package cz.dron.lidarcam

import android.content.Context
import android.os.Build
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * A recording is a folder with
 *   video.mp4    the camera (absent if the camera was not available)
 *   lidar.jsonl  one turn per line: {"t_ns", "hz", "n", "pts": [angle deg, dist mm, intensity, ...]}
 *   meta.json    {"video_start_ns", ...}
 * t_ns and video_start_ns are both SystemClock.elapsedRealtimeNanos(), so a
 * turn sits (t_ns - video_start_ns) / 1e9 seconds into the video. t_ns is
 * when the turn was finished.
 */
object Sessions {
    fun root(ctx: Context) = File(ctx.getExternalFilesDir(null), "sessions")

    fun newDir(ctx: Context): File {
        val name = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss", Locale.ROOT).format(Date())
        return File(root(ctx), name).apply { mkdirs() }
    }

    fun list(ctx: Context): List<File> =
        root(ctx).listFiles { f -> File(f, "meta.json").exists() }?.sortedByDescending { it.name } ?: emptyList()
}

class SessionWriter(val dir: File) {
    private val out = File(dir, "lidar.jsonl").bufferedWriter(bufferSize = 1 shl 16)
    private val startedNs = SystemClock.elapsedRealtimeNanos()
    private var videoStartNs = Long.MAX_VALUE
    private var closed = false
    var scans = 0
        private set

    @Synchronized
    fun write(s: Scan) {
        if (closed) return
        out.write(s.toJson())
        out.write("\n")
        scans++
    }

    /** Called with (now - recorded duration); the smallest guess is the least delayed one. */
    @Synchronized
    fun noteVideoStart(ns: Long) {
        if (ns < videoStartNs) videoStartNs = ns
    }

    @Synchronized
    fun close(hasVideo: Boolean) {
        if (closed) return
        closed = true
        out.close()
        val meta = JSONObject()
            .put("format", "lidarcam/1")
            .put("created", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.ROOT).format(Date()))
            .put("video", hasVideo)
            .put("video_start_ns", if (videoStartNs == Long.MAX_VALUE) startedNs else videoStartNs)
            .put("scans", scans)
            .put("device", Build.MODEL)
            .put("lidar", "LDRobot D500")
        File(dir, "meta.json").writeText(meta.toString(2))
    }
}

class SessionData(val dir: File) {
    val hasVideo: Boolean
    /** Milliseconds into the video, ascending. */
    val timesMs: LongArray
    val scans: List<Scan>

    init {
        val meta = JSONObject(File(dir, "meta.json").readText())
        val start = meta.getLong("video_start_ns")
        hasVideo = meta.optBoolean("video", true) && File(dir, "video.mp4").exists()
        val list = ArrayList<Scan>()
        File(dir, "lidar.jsonl").forEachLine { line ->
            if (line.isBlank()) return@forEachLine
            val o = JSONObject(line)
            val pts: JSONArray = o.getJSONArray("pts")
            val n = pts.length() / 3
            val a = FloatArray(n)
            val d = IntArray(n)
            val q = IntArray(n)
            for (i in 0 until n) {
                a[i] = pts.getDouble(3 * i).toFloat()
                d[i] = pts.getInt(3 * i + 1)
                q[i] = pts.getInt(3 * i + 2)
            }
            list.add(Scan(o.getLong("t_ns"), o.getDouble("hz").toFloat(), a, d, q))
        }
        scans = list
        timesMs = LongArray(list.size) { (list[it].tNanos - start) / 1_000_000 }
    }

    val durationMs get() = if (timesMs.isEmpty()) 0L else timesMs.last()

    /** The last turn finished at or before [ms], or null before the first. */
    fun at(ms: Long): Scan? {
        var lo = 0
        var hi = timesMs.size - 1
        var best = -1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (timesMs[mid] <= ms) { best = mid; lo = mid + 1 } else hi = mid - 1
        }
        return if (best >= 0) scans[best] else null
    }
}
