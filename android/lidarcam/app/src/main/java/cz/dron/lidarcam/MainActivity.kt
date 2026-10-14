package cz.dron.lidarcam

import android.Manifest
import android.app.AlertDialog
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import java.io.File

class MainActivity : ComponentActivity() {
    private lateinit var usb: UsbManager
    private lateinit var preview: PreviewView
    private lateinit var lidarView: LidarView
    private lateinit var status: TextView
    private lateinit var recordButton: Button

    private var lidar: Cp210xLidar? = null
    private var lidarError: String? = null
    @Volatile private var lastScan: Scan? = null
    @Volatile private var session: SessionWriter? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var recording: Recording? = null
    private var recordStartedNs = 0L

    private val ui = Handler(Looper.getMainLooper())
    private val tick = object : Runnable {
        override fun run() {
            updateStatus()
            ui.postDelayed(this, 250)
        }
    }

    private val askCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) startCamera() else Toast.makeText(this, "Bez kamery se nahraje jen lidar", Toast.LENGTH_LONG).show()
    }

    private val usbReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val dev = intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
            when (intent.action) {
                ACTION_USB_PERMISSION ->
                    if (intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false) && dev != null) openLidar(dev)
                    else lidarError = "přístup k USB zamítnut"
                UsbManager.ACTION_USB_DEVICE_DETACHED ->
                    if (dev != null && dev.deviceName == lidar?.device?.deviceName) closeLidar()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        usb = getSystemService(UsbManager::class.java)
        preview = findViewById(R.id.preview)
        lidarView = findViewById(R.id.lidar)
        status = findViewById(R.id.status)
        recordButton = findViewById(R.id.record)
        recordButton.setOnClickListener { toggleRecording() }
        findViewById<Button>(R.id.sessions).setOnClickListener { pickSession() }

        registerReceiver(
            usbReceiver,
            IntentFilter(ACTION_USB_PERMISSION).apply { addAction(UsbManager.ACTION_USB_DEVICE_DETACHED) },
            RECEIVER_NOT_EXPORTED,
        )

        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) startCamera()
        else askCamera.launch(Manifest.permission.CAMERA)

        findLidar(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        findLidar(intent)
    }

    override fun onResume() {
        super.onResume()
        if (lidar == null) findLidar(null)
        ui.post(tick)
    }

    override fun onPause() {
        super.onPause()
        ui.removeCallbacks(tick)
    }

    override fun onDestroy() {
        recording?.stop()
        session?.close(hasVideo = recording != null)
        closeLidar()
        unregisterReceiver(usbReceiver)
        super.onDestroy()
    }

    // --- lidar -------------------------------------------------------------

    private fun findLidar(intent: Intent?) {
        if (lidar != null) return
        val dev = intent?.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
            ?: usb.deviceList.values.firstOrNull { it.vendorId == Cp210xLidar.VENDOR_CP210X }
            ?: return
        if (usb.hasPermission(dev)) {
            openLidar(dev)
        } else {
            val pi = PendingIntent.getBroadcast(
                this, 0, Intent(ACTION_USB_PERMISSION).setPackage(packageName), PendingIntent.FLAG_MUTABLE,
            )
            usb.requestPermission(dev, pi)
        }
    }

    private fun openLidar(dev: UsbDevice) {
        if (lidar != null) return
        val l = Cp210xLidar(usb, dev) { scan ->
            lastScan = scan
            session?.write(scan)
            lidarView.show(scan)
        }
        lidarError = l.start()
        if (lidarError == null) lidar = l
    }

    private fun closeLidar() {
        lidar?.stop()
        lidar = null
        lastScan = null
        lidarView.show(null)
    }

    // --- camera and recording ---------------------------------------------

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val pv = Preview.Builder().build().also { it.surfaceProvider = preview.surfaceProvider }
            val recorder = Recorder.Builder()
                .setQualitySelector(QualitySelector.from(Quality.FHD, FallbackStrategy.lowerQualityOrHigherThan(Quality.HD)))
                .build()
            val vc = VideoCapture.withOutput(recorder)
            provider.unbindAll()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, pv, vc)
            videoCapture = vc
        }, mainExecutor)
    }

    private fun toggleRecording() {
        val running = session
        if (running != null) {
            val rec = recording
            if (rec != null) rec.stop() // the Finalize event closes the session
            else finishSession(running, hasVideo = false, error = null)
            return
        }

        val dir = Sessions.newDir(this)
        val w = SessionWriter(dir)
        session = w
        recordStartedNs = SystemClock.elapsedRealtimeNanos()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        recordButton.text = "■ Zastavit"

        val vc = videoCapture ?: return // lidar only
        recording = vc.output
            .prepareRecording(this, FileOutputOptions.Builder(File(dir, "video.mp4")).build())
            .start(mainExecutor) { ev ->
                when (ev) {
                    is VideoRecordEvent.Status -> {
                        val d = ev.recordingStats.recordedDurationNanos
                        if (d > 0) w.noteVideoStart(SystemClock.elapsedRealtimeNanos() - d)
                    }
                    is VideoRecordEvent.Finalize -> {
                        recording = null
                        val err = if (ev.hasError()) "video: chyba ${ev.error}" else null
                        finishSession(w, hasVideo = !ev.hasError() || File(dir, "video.mp4").length() > 0, error = err)
                    }
                }
            }
    }

    private fun finishSession(w: SessionWriter, hasVideo: Boolean, error: String?) {
        session = null
        w.close(hasVideo)
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        recordButton.text = "● Nahrávat"
        val msg = error ?: "Uloženo: ${w.dir.name} (${w.scans} otáček)"
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
    }

    private fun updateStatus() {
        val l = lidar
        val s = lastScan
        val lidarLine = when {
            l == null -> "lidar: " + (lidarError ?: "připoj D500 do USB-C")
            s == null || SystemClock.elapsedRealtimeNanos() - s.tNanos > 1_000_000_000L -> "lidar: připojen, žádná data"
            else -> "lidar: %.1f Hz · %d bodů · CRC chyb %d".format(s.hz, s.size, l.crcErrors)
        }
        val w = session
        val recLine = if (w == null) {
            if (videoCapture == null) "kamera: nedostupná" else "připraveno"
        } else {
            val sec = (SystemClock.elapsedRealtimeNanos() - recordStartedNs) / 1_000_000_000L
            "● REC %02d:%02d · %d otáček%s".format(sec / 60, sec % 60, w.scans, if (recording == null) " · jen lidar" else "")
        }
        status.text = "$lidarLine\n$recLine"
    }

    private fun pickSession() {
        val list = Sessions.list(this)
        if (list.isEmpty()) {
            Toast.makeText(this, "Zatím žádné záznamy", Toast.LENGTH_SHORT).show()
            return
        }
        val labels = list.map { dir ->
            val mb = (dir.listFiles()?.sumOf { it.length() } ?: 0L) / 1_000_000.0
            "%s  (%.1f MB)".format(dir.name, mb)
        }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("Záznamy")
            .setItems(labels) { _, i ->
                startActivity(Intent(this, PlayerActivity::class.java).putExtra(PlayerActivity.EXTRA_DIR, list[i].absolutePath))
            }
            .show()
    }

    companion object {
        private const val ACTION_USB_PERMISSION = "cz.dron.lidarcam.USB_PERMISSION"
    }
}
