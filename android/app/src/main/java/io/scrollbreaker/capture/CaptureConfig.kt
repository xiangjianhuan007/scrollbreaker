package io.scrollbreaker.capture

import android.content.Context
import android.content.SharedPreferences

/**
 * Everything the app needs to know, and nothing hard-coded.
 *
 * The upstream project this grew out of had the endpoint, the upload topic and the
 * target package compiled into the source. That makes an open-source release
 * impossible: one build would ship someone else's server address. So every value
 * that identifies *you* lives here, is empty by default, and is edited in the UI.
 */
class CaptureConfig(ctx: Context) {

    private val sp: SharedPreferences =
        ctx.getSharedPreferences("scrollbreaker", Context.MODE_PRIVATE)

    /** Master switch. Off means the tick does nothing at all. */
    var enabled: Boolean
        get() = sp.getBoolean("enabled", false)
        set(v) = sp.edit().putBoolean("enabled", v).apply()

    /**
     * Where frames and their hashes are POSTed.
     * Empty = nothing is uploaded (the app still counts frames locally so you can
     * verify capture works before pointing it anywhere).
     */
    var endpoint: String
        get() = sp.getString("endpoint", "") ?: ""
        set(v) = sp.edit().putString("endpoint", v.trim()).apply()

    /** Optional bearer token sent as `Authorization: Bearer <token>`. */
    var token: String
        get() = sp.getString("token", "") ?: ""
        set(v) = sp.edit().putString("token", v.trim()).apply()

    /** Capture interval. 10s is the default; see README for why not 1s. */
    var intervalMs: Long
        get() = sp.getLong("interval_ms", 10_000L)
        set(v) = sp.edit().putLong("interval_ms", v.coerceIn(3_000L, 300_000L)).apply()

    /**
     * Only capture while this package is in the foreground.
     * Empty = capture whatever is in front. Scoping it is the single biggest
     * privacy win available, so the UI pushes you toward setting it.
     */
    var onlyPackage: String
        get() = sp.getString("only_pkg", "") ?: ""
        set(v) = sp.edit().putString("only_pkg", v.trim()).apply()

    /** Upload only on Wi-Fi. Default on: a 10s cadence on mobile data is rude. */
    var wifiOnly: Boolean
        get() = sp.getBoolean("wifi_only", true)
        set(v) = sp.edit().putBoolean("wifi_only", v).apply()

    /** dHash tolerance: bits allowed to differ before it counts as a new frame. */
    var sameBits: Int
        get() = sp.getInt("same_bits", 6)
        set(v) = sp.edit().putInt("same_bits", v.coerceIn(0, 20)).apply()

    /** Longest edge of the uploaded JPEG, and its quality. */
    var maxWidth: Int
        get() = sp.getInt("max_width", 640)
        set(v) = sp.edit().putInt("max_width", v.coerceIn(320, 1600)).apply()

    var quality: Int
        get() = sp.getInt("quality", 60)
        set(v) = sp.edit().putInt("quality", v.coerceIn(30, 90)).apply()

    /** Skip frames that look like a password / payment screen. Hard on, not a toggle. */
    val privacyGate: Boolean get() = true

    fun ready(): Boolean = enabled && endpoint.isNotBlank()
}
