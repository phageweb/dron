package cz.dron.lidarcam

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import androidx.core.graphics.ColorUtils
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/** Top-down view of one lidar turn, front up. Pinch to zoom. Same colours as lidar/index.html. */
class LidarView(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {
    @Volatile private var scan: Scan? = null
    private var rangeMm = 3000f
    private val density = resources.displayMetrics.density

    private val grid = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(0x1d, 0x24, 0x2d); style = Paint.Style.STROKE; strokeWidth = density
    }
    private val label = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(0x5b, 0x66, 0x73); textSize = 11 * density
    }
    private val dot = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        strokeWidth = 3 * density; strokeCap = Paint.Cap.ROUND
    }
    private val near = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(0xff, 0x6b, 0x5b); style = Paint.Style.STROKE; strokeWidth = 2 * density
    }
    private val self = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(0x4c, 0xc2, 0xff); strokeWidth = 2 * density
    }
    private val hud = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(0xd7, 0xdd, 0xe4); textSize = 13 * density; typeface = android.graphics.Typeface.MONOSPACE
    }

    // Intensity 0..255 -> blue .. cyan .. yellow .. near white.
    private val palette = IntArray(256) { q ->
        val t = min(q / 200f, 1f)
        ColorUtils.HSLToColor(floatArrayOf(210f - t * 160f, 0.9f, 0.45f + t * 0.25f))
    }

    private val zoom = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(d: ScaleGestureDetector): Boolean {
            rangeMm = (rangeMm / d.scaleFactor).coerceIn(300f, 12000f)
            invalidate()
            return true
        }
    })

    fun show(s: Scan?) {
        scan = s
        postInvalidateOnAnimation()
    }

    override fun onTouchEvent(e: MotionEvent): Boolean {
        zoom.onTouchEvent(e)
        return true
    }

    override fun onDraw(c: Canvas) {
        c.drawColor(Color.rgb(0x0b, 0x0e, 0x12))
        val cx = width / 2f
        val cy = height / 2f
        val k = min(width, height) / 2f * 0.92f / rangeMm

        val step = listOf(250f, 500f, 1000f, 2000f, 5000f).first { it >= rangeMm / 4 || it == 5000f }
        var r = step
        while (r * k < maxOf(width, height)) {
            c.drawCircle(cx, cy, r * k, grid)
            c.drawText(if (r < 1000) "%.2f m".format(r / 1000) else "%.0f m".format(r / 1000), cx + 4 * density, cy - r * k - 3 * density, label)
            r += step
        }

        val s = scan
        if (s != null) {
            for (i in 0 until s.size) {
                val d = s.dist[i]
                if (d == 0) continue
                val a = Math.toRadians(s.angle[i].toDouble())
                dot.color = palette[s.inten[i]]
                c.drawPoint(cx + (sin(a) * d * k).toFloat(), cy - (cos(a) * d * k).toFloat(), dot)
            }
            val n = s.nearest
            if (n >= 0) {
                val a = Math.toRadians(s.angle[n].toDouble())
                c.drawCircle(cx + (sin(a) * s.dist[n] * k).toFloat(), cy - (cos(a) * s.dist[n] * k).toFloat(), 7 * density, near)
                c.drawText("nejbližší %.2f m @ %.0f°".format(s.dist[n] / 1000f, s.angle[n]), 8 * density, 18 * density, hud)
            }
            c.drawText("%.1f Hz · %d bodů".format(s.hz, s.size), 8 * density, 36 * density, hud)
        }

        c.drawCircle(cx, cy, 4 * density, self)
        c.drawLine(cx, cy, cx, cy - 14 * density, self)
    }
}
