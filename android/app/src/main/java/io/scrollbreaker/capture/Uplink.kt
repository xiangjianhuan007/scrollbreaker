package io.scrollbreaker.capture

import android.util.Log
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * The entire network surface of this app: one POST, no SDK, no analytics.
 *
 * The payload is deliberately dumb — the server decides what to do with a frame.
 * Current shape:
 *
 * ```json
 * {"ts": 1761888000.123, "hash": "1234567890123456789", "w": 640, "h": 1389,
 *  "bytes": 52341, "first": false, "b64": "<jpeg base64, no wrapping>"}
 * ```
 *
 * Set `first` to true on the first frame after start so the receiver knows a new
 * capture session began rather than a continuation.
 */
object Uplink {

    private const val TAG = "ScrollBreaker"
    private const val CONNECT_TIMEOUT_MS = 8_000
    private const val READ_TIMEOUT_MS = 12_000

    fun postFrame(
        cfg: CaptureConfig,
        hash: Long,
        width: Int,
        height: Int,
        jpeg: ByteArray,
        b64: String,
        first: Boolean,
    ): Boolean {
        val endpoint = cfg.endpoint.trim()
        if (endpoint.isEmpty()) return false

        val body = JSONObject()
            .put("ts", System.currentTimeMillis() / 1000.0)
            .put("hash", hash.toString())
            .put("w", width)
            .put("h", height)
            .put("bytes", jpeg.size)
            .put("first", first)
            .put("b64", b64)

        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("User-Agent", "ScrollBreaker-Android/0.1")
                val tok = cfg.token.trim()
                if (tok.isNotEmpty()) setRequestProperty("Authorization", "Bearer $tok")
            }
            val bytes = body.toString().toByteArray(Charsets.UTF_8)
            conn.setFixedLengthStreamingMode(bytes.size)
            BufferedOutputStream(conn.outputStream).use { it.write(bytes) }
            val code = conn.responseCode
            if (code in 200..299) true else {
                Log.w(TAG, "upload rejected: HTTP $code")
                false
            }
        } catch (e: Throwable) {
            Log.w(TAG, "upload failed: ${e.javaClass.simpleName}: ${e.message}")
            false
        } finally {
            try { conn?.disconnect() } catch (_: Throwable) {}
        }
    }

    /**
     * Optional reachability probe for the settings screen.
     * A HEAD to the endpoint; any HTTP response (even 405) means the host is there.
     */
    fun probe(endpoint: String, token: String): String = try {
        if (endpoint.isBlank()) "endpoint 未填写" else {
            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "HEAD"
                connectTimeout = 5_000
                readTimeout = 5_000
                if (token.isNotBlank()) setRequestProperty("Authorization", "Bearer $token")
            }
            val code = try { conn.responseCode } finally { conn.disconnect() }
            "服务器可达：HTTP $code"
        }
    } catch (e: Throwable) {
        "连不上：${e.javaClass.simpleName}"
    }
}
