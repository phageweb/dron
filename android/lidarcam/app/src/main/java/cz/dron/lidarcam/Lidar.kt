package cz.dron.lidarcam

import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbManager
import android.os.SystemClock
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** One turn of the lidar. Angle in degrees clockwise from the front, distance in mm (0 = no return). */
class Scan(
    val tNanos: Long,
    val hz: Float,
    val angle: FloatArray,
    val dist: IntArray,
    val inten: IntArray,
) {
    val size get() = angle.size

    /** Index of the closest valid point, or -1. */
    val nearest: Int by lazy {
        var best = -1
        for (i in 0 until size) if (dist[i] > 0 && (best < 0 || dist[i] < dist[best])) best = i
        best
    }

    fun toJson(): String {
        val sb = StringBuilder(size * 14 + 64)
        sb.append("{\"t_ns\":").append(tNanos)
            .append(",\"hz\":").append("%.2f".format(java.util.Locale.ROOT, hz))
            .append(",\"n\":").append(size)
            .append(",\"pts\":[")
        for (i in 0 until size) {
            if (i > 0) sb.append(',')
            sb.append("%.2f".format(java.util.Locale.ROOT, angle[i])).append(',')
                .append(dist[i]).append(',').append(inten[i])
        }
        return sb.append("]}").toString()
    }
}

/**
 * LD19 / STL-19P protocol as spoken by the D500: 47-byte packets,
 * 0x54 0x2C, speed, start angle, 12 x (distance, intensity), end angle,
 * timestamp, CRC-8. Gathers points into whole turns.
 */
class LidarParser(private val onScan: (Scan) -> Unit) {
    private val buf = ByteArray(8192)
    private var len = 0
    private var angle = FloatArray(1024)
    private var dist = IntArray(1024)
    private var inten = IntArray(1024)
    private var count = 0
    private var lastAngle = -1f
    var crcErrors = 0
        private set

    fun feed(data: ByteArray, n: Int, nowNanos: Long) {
        if (len + n > buf.size) len = 0
        System.arraycopy(data, 0, buf, len, n)
        len += n
        var i = 0
        while (true) {
            while (i + 1 < len && !(buf[i] == 0x54.toByte() && buf[i + 1] == 0x2C.toByte())) i++
            if (i + PACKET > len) break
            if (crc8(buf, i, PACKET - 1) != u8(i + PACKET - 1)) {
                crcErrors++
                i++
                continue
            }
            packet(i, nowNanos)
            i += PACKET
        }
        System.arraycopy(buf, i, buf, 0, len - i)
        len -= i
    }

    private fun u8(o: Int) = buf[o].toInt() and 0xFF
    private fun u16(o: Int) = u8(o) or (u8(o + 1) shl 8)

    private fun packet(o: Int, nowNanos: Long) {
        val speed = u16(o + 2)
        val start = u16(o + 4) / 100f
        val end = u16(o + 42) / 100f
        val step = ((end - start) % 360f + 360f) % 360f / (POINTS - 1)
        for (k in 0 until POINTS) {
            val a = (start + step * k) % 360f
            // The turn wraps past 0 deg, often in the middle of a packet.
            if (lastAngle >= 0 && a < lastAngle - 180f) emit(nowNanos, speed)
            lastAngle = a
            if (count == angle.size) grow()
            angle[count] = a
            dist[count] = u16(o + 6 + 3 * k)
            inten[count] = u8(o + 8 + 3 * k)
            count++
        }
    }

    private fun emit(nowNanos: Long, speed: Int) {
        if (count > 0) {
            onScan(Scan(nowNanos, speed / 360f, angle.copyOf(count), dist.copyOf(count), inten.copyOf(count)))
        }
        count = 0
    }

    private fun grow() {
        angle = angle.copyOf(angle.size * 2)
        dist = dist.copyOf(dist.size * 2)
        inten = inten.copyOf(inten.size * 2)
    }

    companion object {
        const val PACKET = 47
        const val POINTS = 12
        const val BAUD = 230400

        // CRC-8, polynomial 0x4D, as in LDRobot's SDK.
        private val CRC = IntArray(256).also { t ->
            for (i in 0 until 256) {
                var c = i
                repeat(8) { c = if (c and 0x80 != 0) ((c shl 1) xor 0x4D) and 0xFF else (c shl 1) and 0xFF }
                t[i] = c
            }
        }

        fun crc8(b: ByteArray, off: Int, n: Int): Int {
            var c = 0
            for (i in off until off + n) c = CRC[(c xor b[i].toInt()) and 0xFF]
            return c
        }
    }
}

/** The D500 behind its CP2102 bridge, driven directly through the USB host API. */
class Cp210xLidar(
    private val usb: UsbManager,
    val device: UsbDevice,
    private val onScan: (Scan) -> Unit,
) {
    @Volatile private var running = false
    private var thread: Thread? = null
    private var conn: UsbDeviceConnection? = null
    private var parser: LidarParser? = null
    val crcErrors get() = parser?.crcErrors ?: 0

    fun start(): String? {
        val c = usb.openDevice(device) ?: return "nelze otevřít USB zařízení"
        val iface = device.getInterface(0)
        if (!c.claimInterface(iface, true)) {
            c.close()
            return "nelze převzít USB rozhraní"
        }
        val epIn = (0 until iface.endpointCount).map { iface.getEndpoint(it) }.firstOrNull {
            it.type == UsbConstants.USB_ENDPOINT_XFER_BULK && it.direction == UsbConstants.USB_DIR_IN
        }
        if (epIn == null) {
            c.close()
            return "CP2102 nemá vstupní endpoint"
        }
        val idx = iface.id
        fun ctl(req: Int, value: Int, data: ByteArray? = null) =
            c.controlTransfer(0x41, req, value, idx, data, data?.size ?: 0, 1000)
        ctl(0x00, 0x0001) // IFC_ENABLE
        ctl(0x1E, 0, ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(LidarParser.BAUD).array()) // SET_BAUDRATE
        ctl(0x03, 0x0800) // SET_LINE_CTL: 8 data bits, no parity, 1 stop bit
        ctl(0x07, 0x0303) // SET_MHS: DTR and RTS on
        ctl(0x12, 0x000F) // PURGE: drop whatever was buffered before

        conn = c
        running = true
        thread = Thread({ loop(c, epIn) }, "lidar-usb").apply { start() }
        return null
    }

    private fun loop(c: UsbDeviceConnection, ep: UsbEndpoint) {
        val p = LidarParser(onScan)
        parser = p
        // Small reads keep the latency down: 512 B is ~22 ms of data at 230400 Bd.
        val b = ByteArray(512)
        while (running) {
            val n = c.bulkTransfer(ep, b, b.size, 300)
            if (n > 0) p.feed(b, n, SystemClock.elapsedRealtimeNanos())
        }
    }

    fun stop() {
        running = false
        thread?.join(1000)
        thread = null
        conn?.let {
            it.releaseInterface(device.getInterface(0))
            it.close()
        }
        conn = null
    }

    companion object {
        const val VENDOR_CP210X = 0x10C4
    }
}
