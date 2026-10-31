package io.scrollbreaker.capture

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlin.math.sqrt

/**
 * Perceptual hashing + blank-screen detection.
 *
 * Both are pure functions over a JPEG byte array so they can be exercised without
 * an Android device (see `app/src/test/`).
 *
 * Why dHash and not aHash: dHash compares *neighbouring* pixels, so a uniform
 * brightness change (screen dims, status bar goes from light to dark) barely moves
 * the hash. aHash compares every pixel to the mean and would report "new frame"
 * every time the backlight shifts.
 */
object ImageSig {

    /** Downscale target for hashing: one extra column so there are 8 horizontal comparisons per row. */
    private const val HASH_W = 9
    private const val HASH_H = 8

    /** Downscale target for blank detection (mean / std over a coarse grid). */
    private const val BLANK_N = 48

    /**
     * 64-bit difference hash.
     * Returns 0 on failure — callers treat 0 as "no hash yet", never as "identical".
     */
    fun dhash(jpeg: ByteArray): Long = try {
        val src = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size) ?: return 0L
        val small = Bitmap.createScaledBitmap(src, HASH_W, HASH_H, true)
        src.recycle()
        var h = 0L
        for (y in 0 until HASH_H) {
            for (x in 0 until HASH_W - 1) {
                val a = luma(small.getPixel(x, y))
                val b = luma(small.getPixel(x + 1, y))
                h = (h shl 1) or (if (a > b) 1L else 0L)
            }
        }
        small.recycle()
        h
    } catch (_: Throwable) {
        0L
    }

    /** Hamming distance between two hashes: how many bits differ. */
    fun distance(a: Long, b: Long): Int = java.lang.Long.bitCount(a xor b)

    /**
     * True when the two frames are effectively the same picture.
     *
     * [tolerance] = number of bits allowed to differ. 6 is the value that survived
     * real testing: it absorbs cursor blink, clock ticks and JPEG noise while still
     * catching a genuine scroll.
     */
    fun sameFrame(prev: Long, cur: Long, tolerance: Int): Boolean =
        prev != 0L && cur != 0L && distance(prev, cur) <= tolerance

    /**
     * Blank / near-uniform frame (screen off, solid colour, lock screen flash).
     * Returns true if either the mean brightness is very low or the variance is tiny.
     *
     * OCR on a blank frame legitimately yields nothing — treat that as "nothing to
     * capture", not as an error. Early versions logged it as a failure and the logs
     * filled with phantom problems.
     */
    fun isBlank(jpeg: ByteArray): Boolean = try {
        val src = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size) ?: return false
        val s = Bitmap.createScaledBitmap(src, BLANK_N, BLANK_N, true)
        src.recycle()
        var sum = 0.0
        var sumSq = 0.0
        for (y in 0 until BLANK_N) {
            for (x in 0 until BLANK_N) {
                val g = luma(s.getPixel(x, y)).toDouble()
                sum += g
                sumSq += g * g
            }
        }
        s.recycle()
        val n = (BLANK_N * BLANK_N).toDouble()
        val mean = sum / n
        val variance = sumSq / n - mean * mean
        val std = if (variance > 0) sqrt(variance) else 0.0
        mean < 12.0 || std < 3.0
    } catch (_: Throwable) {
        false
    }

    /** ITU-R BT.601 luma. */
    private fun luma(c: Int): Int =
        (((c shr 16 and 0xFF) * 299 + (c shr 8 and 0xFF) * 587 + (c and 0xFF) * 114) / 1000)
}
