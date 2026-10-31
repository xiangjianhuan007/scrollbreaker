package io.scrollbreaker.capture

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/**
 * Settings screen. Built in code on purpose — no XML layouts, no Compose, no
 * resource plumbing. The whole app is ~700 lines; a layout file per row would be
 * more ceremony than the feature deserves.
 */
class MainActivity : Activity() {

    private lateinit var cfg: CaptureConfig
    private lateinit var status: TextView
    private lateinit var endpointField: EditText
    private lateinit var tokenField: EditText
    private lateinit var pkgField: EditText
    private lateinit var intervalField: EditText
    private lateinit var enableBox: CheckBox
    private lateinit var wifiBox: CheckBox

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = CaptureConfig(this)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(24))
        }

        root.addView(title("ScrollBreaker Capture"))
        root.addView(hint(
            "定时截屏 → 感知哈希去重 → POST 到你的服务器。\n" +
                "不读聊天数据库，不注入进程，不联网除非你填了 endpoint。"
        ))

        // ---- master switch ----
        enableBox = CheckBox(this).apply {
            text = "启用采集"
            isChecked = cfg.enabled
        }
        root.addView(enableBox)

        // ---- endpoint ----
        root.addView(label("上报地址（POST JSON，留空则只本地计数）"))
        endpointField = input(cfg.endpoint, "https://your-server.example/capture")
        root.addView(endpointField)

        root.addView(label("Bearer token（可选）"))
        tokenField = input(cfg.token, "")
        tokenField.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        root.addView(tokenField)

        // ---- scope ----
        root.addView(label("只在前台是此包名时采集（强烈建议填，留空=任意界面）"))
        pkgField = input(cfg.onlyPackage, "com.tencent.mm")
        root.addView(pkgField)

        // ---- interval ----
        root.addView(label("采集间隔（秒，3~300）"))
        intervalField = input((cfg.intervalMs / 1000).toString(), "10")
        intervalField.inputType = InputType.TYPE_CLASS_NUMBER
        root.addView(intervalField)

        // ---- wifi ----
        wifiBox = CheckBox(this).apply {
            text = "只在 Wi-Fi 下采集/上传"
            isChecked = cfg.wifiOnly
        }
        root.addView(wifiBox)

        // ---- actions ----
        root.addView(button("保存设置") {
            save()
            toast("已保存")
        })
        root.addView(button("打开无障碍设置（需要手动开启本服务）") {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        })
        root.addView(button("测试服务器连通性") {
            save()
            toast(Uplink.probe(cfg.endpoint, cfg.token))
        })
        root.addView(button("立刻采一帧") {
            save()
            val ok = CaptureService.pokeNow()
            toast(if (ok) "已触发（需服务已开启）" else "服务未连接，先在无障碍里开启")
        })

        // ---- status ----
        status = TextView(this).apply {
            setPadding(0, dp(16), 0, 0)
            textSize = 13f
        }
        root.addView(status)

        setContentView(ScrollView(this).apply { addView(root) })
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    private fun refreshStatus() {
        val on = CaptureService.running
        status.text = buildString {
            appendLine("服务状态：${if (on) "运行中" else "未连接"}")
            appendLine("最近一次：${CaptureService.lastNote}")
            appendLine("已采集 ${CaptureService.shotCount} 帧 / 跳过 ${CaptureService.skipCount} 次")
            appendLine()
            append("隐私闸门：密码/支付界面一律跳过（不可关闭）")
        }
    }

    private fun save() {
        cfg.enabled = enableBox.isChecked
        cfg.endpoint = endpointField.text.toString()
        cfg.token = tokenField.text.toString()
        cfg.onlyPackage = pkgField.text.toString()
        val secs = intervalField.text.toString().toLongOrNull() ?: 10L
        cfg.intervalMs = secs.coerceIn(3, 300) * 1000
        cfg.wifiOnly = wifiBox.isChecked
    }

    // ---- tiny UI helpers ----
    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun title(t: String) = TextView(this).apply {
        text = t; textSize = 22f; setPadding(0, 0, 0, dp(8))
    }

    private fun label(t: String) = TextView(this).apply {
        text = t; textSize = 13f; setPadding(0, dp(16), 0, dp(4))
    }

    private fun hint(t: String) = TextView(this).apply {
        text = t; textSize = 13f; setPadding(0, dp(4), 0, dp(12))
    }

    private fun input(value: String, placeholder: String) = EditText(this).apply {
        setText(value)
        this.hint = placeholder
        inputType = InputType.TYPE_CLASS_TEXT
        textSize = 14f
    }

    private fun button(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        setOnClickListener { onClick() }
    }

    private fun toast(msg: String) =
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
}
