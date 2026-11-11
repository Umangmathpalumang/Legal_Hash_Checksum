# LHC Pro — Desktop App (Mac + Windows)

Built with **Electron** — wraps the existing FastAPI server in a native window.

## Prerequisites

- **Node.js 18+** — https://nodejs.org
- **Python 3.10+** with the project's `.venv` already set up (run `pip install -r requirements.txt` in the project root first)

## Run in development

```bash
cd desktop
npm install
# In a separate terminal, start the FastAPI server:
cd .. && source .venv/bin/activate && uvicorn main:app --port 18765
# Back in desktop/
npm start
```

## Build distributable

```bash
cd desktop
npm install

# Mac (.dmg — runs on Intel + Apple Silicon)
npm run build:mac

# Windows (.exe installer + portable)
npm run build:win

# Both at once (requires both platforms or CI)
npm run build
```

Output goes to `desktop/dist/`.

## Icon files (required before building)

Place the following in `desktop/build/`:
- `icon.icns` — Mac app icon (use https://www.icoconverter.com or `iconutil` on Mac)
- `icon.ico` — Windows icon
- `icon.png` — 256×256 fallback

You can generate these from the project's `favicon.svg`.

## License binding (MAC address)

When running as a desktop app, `lhc-core.js` calls `window.__LHCDesktop.getDeviceId()` via the Electron preload bridge. This returns the real network interface MAC address (not a browser fingerprint). Use this to bind Pro licenses to a specific machine:

```json
{ "mac": "a4:83:e7:xx:xx:xx", "platform": "darwin", "hostname": "MacBook-Pro" }
```

## iOS & Android (PWA)

The web app is already a PWA (manifest.json + service worker). No extra build step needed:
- **Android Chrome**: visit the URL → browser shows "Add to Home Screen" banner → installs as a standalone app
- **iOS Safari**: visit the URL → Share → "Add to Home Screen" → installs with the LHC Pro icon

For full App Store / Play Store distribution, use **Capacitor**:
```bash
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npx cap init "LHC Pro" com.legalhashchecksum.pro
npx cap add android  # requires Android Studio
npx cap add ios      # requires Xcode on Mac
npx cap sync
npx cap open android
npx cap open ios
```
