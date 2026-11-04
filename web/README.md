# Custom GoTo Mobile Web App

Professional mobile & browser control companion for the **Custom GoTo Telescope Mount**.

Designed for field observation with pure-red rhodopsin-preserving dark sky aesthetics, touch-optimized manual motion D-pad, live polar sky radar, curated object catalog, and motorized focus control.

---

## Features

- **Dark-Sky Night Vision UI**: Pure-red `#FF3333` and OLED-black `#000000` theme compliant with dark-adaptation astronomy standards.
- **Live Mount Telemetry**: Real-time Alt/Az, RA/Dec (J2000), slew state (`IDLE`, `SLEWING`, `TRACKING`, `PARKED`), and data rates.
- **Celestial Sky Radar**: Interactive SVG polar projection rendering horizon, altitude rings, cardinal markers, mount reticle, and target reticle.
- **Eyepiece Motion D-Pad**: Variable-rate manual slewing with Fine ($0.05^\circ$), Medium ($0.50^\circ$), and Coarse ($3.00^\circ$) steps.
- **Target Catalog & GoTo**: Instant 1-tap GoTo slewing for major planets, Moon, Messier & Caldwell deep-sky targets, plus manual coordinate entry.
- **Motorized Focus Control**: Step presets ($\pm 5, \pm 50$ steps), numeric nudge, and position zeroing.
- **Safety Interlocks**: Prominent Emergency `STOP` button and solar keepout warnings.
- **Built-in Virtual Simulator**: Test and explore all controls in-browser without needing the physical mount connected.

---

## Local Development

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Deploy to Vercel (1-Click)

1. Push your repository to GitHub.
2. In the [Vercel Dashboard](https://vercel.com/new), import your `Custom-GoTo-Telescope` repository.
3. In **Root Directory**, click **Edit** and select `web`.
4. Leave framework preset as **Next.js** and click **Deploy**.
5. Your web app is live at `https://your-project.vercel.app`!

---

## Connecting to Your Physical Telescope

1. Start the desktop app or Python bridge (`python telescope_ui_qt.py`). The local Web Bridge server automatically starts on port `8080`.
2. In the mobile web app, tap the **Settings** icon (top right).
3. Disable **Virtual Mount Simulator**.
4. Set the **Telescope Bridge URL**:
   - **On the same Wi-Fi / Laptop Hotspot**: `http://<YOUR_LAPTOP_LOCAL_IP>:8080` (e.g. `http://192.168.1.105:8080`).
   - **Anywhere in the world (Remote)**: Your secure Cloudflare Tunnel or ngrok URL (e.g. `https://telescope.yourdomain.com`).
5. (Optional) Enter your Secret Access Token/PIN if configured.
6. Tap **Save Settings**. Your web app will now stream live telemetry and command the physical mount!
