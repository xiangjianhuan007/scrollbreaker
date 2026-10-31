# ScrollBreaker Capture (Android)

The phone half of ScrollBreaker: capture the screen on an interval, drop frames that
haven't changed, refuse to capture password screens, and POST the rest to an endpoint
you control.

This is the source of the capture client — **not** a turnkey product. You build it
yourself, and nothing leaves your device until you enter an endpoint.

## What it does, in order

```
enabled?            no  -> do nothing
Wi-Fi only?         no  -> skip
foreground matches? no  -> skip        (scope it to one app; this is the big privacy win)
looks private?      yes -> SKIP        (password / payment / login markers — not configurable)
too small / blank?  yes -> skip
same dHash?         yes -> skip        (this is what makes a 10s cadence affordable)
encode -> POST json
```

## Why an AccessibilityService

There is no other way to screenshot unattended. `MediaProjection` requires a consent
dialog per capture session, which makes a background loop impossible. So the app binds
as an accessibility service and uses `takeScreenshot()` (API 30+).

The service declares two capabilities and uses them narrowly:

| Capability | Used for |
|---|---|
| `canTakeScreenshot` | the capture itself |
| `canRetrieveWindowContent` | **only** the privacy gate — walk the node tree, look for a password-flagged input or marker words, return a boolean |

The node tree is read and discarded. No text from it is stored, logged or uploaded.
`onAccessibilityEvent` is an empty override: this service does not observe typing,
notifications or window changes.

If that trade-off is not acceptable to you, delete `looksPrivate()` and set
`canRetrieveWindowContent="false"` — you lose the password-screen guard, which we
think is the wrong trade, but it's your device.

## Build

```bash
cd android
./gradlew assembleDebug        # -> app/build/outputs/apk/debug/app-debug.apk
```

Requires JDK 17+ and Android SDK with build-tools for API 35. `minSdk` is 30, so
Android 11 and up.

Install the debug APK, open the app, fill in:

- **上报地址 / endpoint** — where frames are POSTed. Leave empty to capture without
  uploading (useful to check the loop works before pointing it anywhere).
- **Bearer token** — optional.
- **只在前台是此包名时采集 / only this package** — strongly recommended.
- **采集间隔 / interval** — seconds, default 10.
- **只在 Wi-Fi 下** — default on.

Then open **Settings → Accessibility → ScrollBreaker Capture** and enable it. The
service can't be enabled from inside the app, by design.

## Payload

```json
{"ts": 1761888000.123, "hash": "1234567890123456789", "w": 640, "h": 1389,
 "bytes": 52341, "first": false, "b64": "<jpeg base64, no wrapping>"}
```

`first: true` marks the first frame of a session. Your server decodes `b64`, OCRs it,
and feeds the text into the Python side (`../`), which is where the page-boundary
logic lives.

Minimal receiver (Python, no framework):

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import base64, json

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        open(f"frame_{body['ts']:.3f}.jpg", "wb").write(base64.b64decode(body["b64"]))
        self.send_response(204); self.end_headers()

HTTPServer(("0.0.0.0", 8080), H).serve_forever()
```

## Costs

A 640-wide JPEG at q60 is roughly 40–60 KB. At a 10 s cadence with dHash dedup, a
heavy reading session uploads a few MB per hour; an idle phone uploads nothing. Wi-Fi
only is the default.

## Not included, on purpose

The upstream internal build also had: accessibility-driven UI navigation, an input
method hook, voice recording upload, and a command channel for remote control. Those
are deliberately absent here — they need capabilities this project should not ask for,
and they're not needed for capture.

## License

MIT, same as the parent project. Build it, fork it, ship it — no warranty.
