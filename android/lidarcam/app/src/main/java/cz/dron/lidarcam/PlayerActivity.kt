package cz.dron.lidarcam

import android.app.AlertDialog
import android.os.Bundle
import android.os.SystemClock
import android.widget.Button
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import android.widget.VideoView
import androidx.activity.ComponentActivity
import java.io.File
import kotlin.concurrent.thread

/** Plays a recording: the video on top, the lidar turn of the same moment below. */
class PlayerActivity : ComponentActivity() {
    private lateinit var video: VideoView
    private lateinit var lidarView: LidarView
    private lateinit var seek: SeekBar
    private lateinit var playButton: Button
    private lateinit var time: TextView

    private var data: SessionData? = null
    private var durationMs = 0L
    private var seeking = false

    // Clock for a recording without video.
    private var playing = false
    private var clockBaseMs = 0L
    private var clockStartedAt = 0L

    private val frame = object : Runnable {
        override fun run() {
            render()
            lidarView.postOnAnimation(this)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_player)
        val dir = File(intent.getStringExtra(EXTRA_DIR)!!)
        findViewById<TextView>(R.id.title).text = dir.name + "\nnačítám…"
        video = findViewById(R.id.video)
        lidarView = findViewById(R.id.lidar)
        seek = findViewById(R.id.seek)
        playButton = findViewById(R.id.play)
        time = findViewById(R.id.time)

        playButton.setOnClickListener { setPlaying(!isPlaying()) }
        findViewById<Button>(R.id.delete).setOnClickListener { confirmDelete(dir) }
        seek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(sb: SeekBar, p: Int, fromUser: Boolean) {
                if (fromUser) seekTo(p.toLong())
            }
            override fun onStartTrackingTouch(sb: SeekBar) { seeking = true }
            override fun onStopTrackingTouch(sb: SeekBar) { seeking = false }
        })

        thread(name = "load-session") {
            val d = try {
                SessionData(dir)
            } catch (e: Exception) {
                runOnUiThread {
                    Toast.makeText(this, "Nelze načíst: ${e.message}", Toast.LENGTH_LONG).show()
                    finish()
                }
                return@thread
            }
            runOnUiThread { loaded(d) }
        }
    }

    private fun loaded(d: SessionData) {
        data = d
        findViewById<TextView>(R.id.title).text = "${d.dir.name}\n${d.scans.size} otáček lidaru" +
            if (d.hasVideo) "" else " · bez videa"
        if (d.hasVideo) {
            video.setVideoPath(File(d.dir, "video.mp4").path)
            video.setOnPreparedListener { mp ->
                durationMs = maxOf(mp.duration.toLong(), d.durationMs)
                seek.max = durationMs.toInt()
                video.seekTo(1) // show the first frame
            }
            video.setOnCompletionListener { playButton.text = "▶" }
        } else {
            video.visibility = android.view.View.GONE
            durationMs = d.durationMs
            seek.max = durationMs.toInt()
        }
        lidarView.postOnAnimation(frame)
    }

    override fun onPause() {
        super.onPause()
        setPlaying(false)
    }

    override fun onDestroy() {
        lidarView.removeCallbacks(frame)
        super.onDestroy()
    }

    private fun isPlaying() = if (data?.hasVideo == true) video.isPlaying else playing

    private fun positionMs(): Long =
        if (data?.hasVideo == true) video.currentPosition.toLong()
        else if (playing) minOf(durationMs, clockBaseMs + SystemClock.elapsedRealtime() - clockStartedAt)
        else clockBaseMs

    private fun setPlaying(on: Boolean) {
        val d = data ?: return
        if (d.hasVideo) {
            if (on) video.start() else video.pause()
        } else {
            clockBaseMs = positionMs().let { if (on && it >= durationMs) 0L else it }
            clockStartedAt = SystemClock.elapsedRealtime()
            playing = on
        }
        playButton.text = if (on) "❚❚" else "▶"
    }

    private fun seekTo(ms: Long) {
        if (data?.hasVideo == true) video.seekTo(ms.toInt())
        else {
            clockBaseMs = ms
            clockStartedAt = SystemClock.elapsedRealtime()
        }
    }

    private fun render() {
        val d = data ?: return
        val pos = positionMs()
        if (!d.hasVideo && playing && pos >= durationMs) setPlaying(false)
        lidarView.show(d.at(pos))
        if (!seeking) seek.progress = pos.toInt()
        time.text = "%s / %s".format(fmt(pos), fmt(durationMs))
    }

    private fun fmt(ms: Long) = "%02d:%02d.%d".format(ms / 60000, ms / 1000 % 60, ms / 100 % 10)

    private fun confirmDelete(dir: File) {
        AlertDialog.Builder(this)
            .setMessage("Smazat záznam ${dir.name}?")
            .setPositiveButton("Smazat") { _, _ ->
                dir.deleteRecursively()
                finish()
            }
            .setNegativeButton("Zrušit", null)
            .show()
    }

    companion object {
        const val EXTRA_DIR = "dir"
    }
}
