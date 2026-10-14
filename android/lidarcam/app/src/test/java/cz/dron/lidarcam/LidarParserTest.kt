package cz.dron.lidarcam

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** d500_sample.bin is ~0.7 s of raw serial bytes from the real D500 (10 Hz, ~500 points a turn). */
class LidarParserTest {
    private val sample = javaClass.getResourceAsStream("/d500_sample.bin")!!.readBytes()

    private fun parse(chunk: Int): Pair<List<Scan>, Int> {
        val scans = ArrayList<Scan>()
        val p = LidarParser { scans.add(it) }
        var o = 0
        while (o < sample.size) {
            val n = minOf(chunk, sample.size - o)
            p.feed(sample.copyOfRange(o, o + n), n, o.toLong())
            o += n
        }
        return scans to p.crcErrors
    }

    @Test
    fun wholeTurnsAreSplitAtZeroDegrees() {
        val (scans, crc) = parse(512)
        assertEquals(0, crc)
        // The first turn is partial (we started mid-turn); the rest are whole.
        val whole = scans.drop(1)
        assertTrue("expected at least two whole turns, got ${whole.size}", whole.size >= 2)
        for (s in whole) {
            assertTrue("points per turn ${s.size}", s.size in 480..520)
            assertTrue(s.angle.first() < 2f && s.angle.last() > 358f)
            assertTrue(s.hz in 9f..11f)
        }
    }

    @Test
    fun chunkSizeDoesNotMatter() {
        val a = parse(512).first.map { it.size }
        val b = parse(7).first.map { it.size }
        val c = parse(64).first.map { it.size }
        assertEquals(a, b)
        assertEquals(a, c)
    }

    @Test
    fun jsonUsesDotsAndTriples() {
        val s = parse(512).first[1]
        val json = s.toJson()
        assertTrue(json.startsWith("{\"t_ns\":"))
        val pts = json.substringAfter("\"pts\":[").substringBefore("]").split(",")
        assertEquals(s.size * 3, pts.size)
    }
}
