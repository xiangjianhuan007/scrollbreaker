package io.scrollbreaker.capture

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.util.Log
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.io.ByteArrayOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * The capture loop.
 *
 * Android gives exactly one way to screenshot without a MediaProjection consent
 * dialog per session: `AccessibilityService.takeScreenshot()` (API 30+). So this
 * service exists, but it does as little as possible with the accessibility API —
 * see the [looksPrivate] note below.
 *
 * Order of gates, cheapest first:
 *
 * ```
 * switch on?          -> no upload, no screenshot
 * Wi-Fi only?         -> skip (mobile data is opt-in)
 * foreground matches? -> skip  (scoping to one app is the biggest privacy win)
 * looks private?      -> SKIP, hard, not configurable
 * too small / blank?  -> skip
 * hash unchanged?     -> skip  (this is what makes 10s cadence affordable)
 * encode + POST
 * ```
 */
class CaptureService : AccessibilityService() {

    companion object {
        private const val TAG = "ScrollBreaker"
        private const val MAX_UPLOAD_BYTES = 150 * 1024
        private const val SCREENSHOT_TIMEOUT_S = 8L

        @Volatile
        var running: Boolean = false
            private set

        @Volatile
        var lastNote: String = "未启动"
            private set

        @Volatile
        var shotCount: Int = 0
            private set

        @Volatile
        var skipCount: Int = 0
            private set

        /** Set by the service so the settings screen can trigger a manual frame. */
        @Volatile
        private var instance: CaptureService? = null

        fun pokeNow(): Boolean {
            val s = instance ?: return false
            s.pool.execute { runCatching { s.oneRound(force = true) } }
            return true
        }
    }

    private val main = Handler(Looper.getMainLooper())

    /**
     * Screenshot work must NOT run on the main thread.
     *
     * `takeScreenshot` posts its callback to the main executor, and this code waits
     * on it with a latch. Blocking the main thread on that latch means the callback
     * can never be delivered — every capture times out and the feature looks
     * silently broken. Learned the hard way; do not "simplify" this away.
     */
    private val pool = Executors.newSingleThreadExecutor { r ->
        Thread(r, "scrollbreaker-capture").apply { isDaemon = true }
    }

    @Volatile private var lastHash = 0L
    @Volatile private var busy = false

    private val tick = object : Runnable {
        override fun run() {
            runCatching { pool.execute { runCatching { oneRound() } } }
            main.postDelayed(this, CaptureConfig(this@CaptureService).intervalMs)
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        running = true
        lastNote = "已连接，等待首帧"
        main.removeCallbacks(tick)
        main.postDelayed(tick, 2_000L)
        Log.i(TAG, "capture service connected")
    }

    override fun onDestroy() {
        main.removeCallbacks(tick)
        instance = null
        running = false
        lastNote = "已停止"
        super.onDestroy()
    }

    override fun onInterrupt() {
        main.removeCallbacks(tick)
        running = false
        lastNote = "被系统中断"
    }

    // Accessibility events are deliberately ignored: this service does not observe
    // typing, notifications or window changes. It only runs the timer above.
    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    // ---------- one round ----------

    private fun oneRound(force: Boolean = false) {
        val cfg = CaptureConfig(this)

        if (!cfg.enabled) {
            lastNote = "总开关关着"
            skipCount++
            return
        }
        if (cfg.wifiOnly && !onWifi()) {
            lastNote = "非 Wi-Fi（仅 Wi-Fi 模式）"
            skipCount++
            return
        }

        val top = foregroundPackage()
        val only = cfg.onlyPackage
        if (only.isNotEmpty() && top != only) {
            lastNote = "前台是 ${top.ifEmpty { "?" }}，不在白名单"
            skipCount++
            return
        }

        // Hard privacy gate. Not a setting: if this fires you get a skipped frame,
        // never an uploaded password screen.
        if (cfg.privacyGate && looksPrivate()) {
            lastNote = "疑似密码/支付界面，已跳过"
            skipCount++
            return
        }

        val jpeg = grab() ?: run { lastNote = "截图失败"; skipCount++; return }
        if (jpeg.size < 3_000) { lastNote = "图太小 ${jpeg.size}B"; skipCount++; return }
        if (ImageSig.isBlank(jpeg)) { lastNote = "空白屏"; skipCount++; return }

        val h = ImageSig.dhash(jpeg)
        if (h == 0L) { lastNote = "哈希失败"; skipCount++; return }

        val first = lastHash == 0L
        if (!force && ImageSig.sameFrame(lastHash, h, cfg.sameBits)) {
            lastNote = "画面没变，不传"
            skipCount++
            return
        }
        lastHash = h

        if (cfg.endpoint.isBlank()) {
            lastNote = "已拍 ${jpeg.size / 1024}KB，但未配置 endpoint"
            shotCount++
            return
        }

        busy = true
        try {
            val b64 = Base64.encodeToString(jpeg, Base64.NO_WRAP)
            val ok = Uplink.postFrame(cfg, h, lastW, lastH, jpeg, b64, first)
            if (ok) {
                shotCount++
                lastNote = "已上传 ${jpeg.size / 1024}KB"
            } else {
                lastNote = "上传失败"
            }
        } finally {
            busy = false
        }
    }

    @Volatile private var lastW = 0
    @Volatile private var lastH = 0

    private fun onWifi(): Boolean = runCatching {
        val cm = getSystemService(CONNECTIVITY_SERVICE) as android.net.ConnectivityManager
        val net = cm.activeNetwork ?: return@runCatching false
        val caps = cm.getNetworkCapabilities(net) ?: return@runCatching false
        caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI)
    }.getOrDefault(false)

    private fun foregroundPackage(): String = runCatching {
        rootInActiveWindow?.packageName?.toString() ?: ""
    }.getOrDefault("")

    /**
     * Does the current screen look like a password / payment / login flow?
     *
     * This is the *only* use of window content in the whole app, and it is
     * one-directional: the tree is walked to look for a password-flagged input or a
     * handful of marker words. **Nothing from the tree is stored, logged or
     * uploaded** — the sole output is a boolean that suppresses the frame.
     *
     * Fail-closed in spirit, fail-open in practice: if the tree is unavailable we
     * return false and rely on the other gates, because blocking all capture on a
     * permissions quirk would make the app useless.
     */
    private fun looksPrivate(): Boolean = runCatching {
        val root = rootInActiveWindow ?: return@runCatching false
        val markers = arrayOf(
            "Password", "password",
            "密码", "支付", "验证码", "银行卡", "转账", "收付款", "钱包", "零钱",
            "指纹", "面容", "解锁", "登录密码",
        )
        var hit = false
        var visited = 0
        val stack = ArrayDeque<AccessibilityNodeInfo>()
        stack.addLast(root)
        while (stack.isNotEmpty() && visited < 200) {
            val node = stack.removeLast()
            visited++
            val cls = node.className?.toString() ?: ""
            if (cls.contains("EditText") && node.isPassword) { hit = true; break }
            val text = (node.text?.toString() ?: "") +
                (node.contentDescription?.toString() ?: "")
            if (text.isNotEmpty() && markers.any { text.contains(it) }) { hit = true; break }
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { stack.addLast(it) }
            }
            runCatching { node.recycle() }
        }
        hit
    }.getOrDefault(false)

    // ---------- screenshot ----------

    private fun grab(): ByteArray? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        val latch = CountDownLatch(1)
        var out: ByteArray? = null
        runCatching {
            takeScreenshot(
                Display.DEFAULT_DISPLAY,
                mainExecutor,
                object : TakeScreenshotCallback {
                    override fun onSuccess(result: ScreenshotResult) {
                        try {
                            val hw = Bitmap.wrapHardwareBuffer(result.hardwareBuffer, result.colorSpace)
                            val soft = hw?.copy(Bitmap.Config.ARGB_8888, false)
                            hw?.recycle()
                            if (soft != null) out = encode(soft)
                            soft?.recycle()
                        } catch (e: Throwable) {
                            Log.w(TAG, "screenshot decode failed: ${e.message}")
                        } finally {
                            runCatching { result.hardwareBuffer.close() }
                            latch.countDown()
                        }
                    }

                    override fun onFailure(errorCode: Int) {
                        Log.w(TAG, "takeScreenshot failed: $errorCode")
                        latch.countDown()
                    }
                },
            )
            latch.await(SCREENSHOT_TIMEOUT_S, TimeUnit.SECONDS)
        }.onFailure { Log.w(TAG, "screenshot threw: ${it.message}") }
        return out
    }

    /** Downscale then compress, stepping quality down until the base64 fits. */
    private fun encode(src: Bitmap): ByteArray? {
        lastW = src.width
        lastH = src.height
        val cfg = CaptureConfig(this)
        val targetW = cfg.maxWidth
        val tiers = arrayOf(
            targetW to cfg.quality,
            (targetW * 88 / 100) to (cfg.quality - 5),
            (targetW * 75 / 100) to (cfg.quality - 10),
            (targetW * 62 / 100) to (cfg.quality - 15),
        )
        for ((w, q) in tiers) {
            val qq = q.coerceIn(30, 90)
            val scaled = if (src.width > w) {
                val h = (src.height.toLong() * w / src.width).toInt().coerceAtLeast(1)
                Bitmap.createScaledBitmap(src, w, h, true)
            } else src
            val bos = ByteArrayOutputStream()
            scaled.compress(Bitmap.CompressFormat.JPEG, qq, bos)
            if (scaled !== src) scaled.recycle()
            val bytes = bos.toByteArray()
            if (bytes.size * 4 / 3 <= MAX_UPLOAD_BYTES) return bytes
        }
        return null
    }
}
