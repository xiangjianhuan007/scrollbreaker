package io.scrollbreaker.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Nothing to start here on modern Android: an AccessibilityService is started by the
 * system once the user enables it, and it survives reboots on its own.
 *
 * This receiver exists only to log the boot so a user debugging "why did it stop
 * capturing after a restart" has something in logcat to look at. It does **not**
 * try to auto-enable anything — enabling accessibility requires an explicit user
 * action and should stay that way.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            val cfg = CaptureConfig(context)
            Log.i(
                "ScrollBreaker",
                "boot completed; enabled=${cfg.enabled}, " +
                    "endpointSet=${cfg.endpoint.isNotBlank()}, " +
                    "serviceConnected=${CaptureService.running}",
            )
        }
    }
}
