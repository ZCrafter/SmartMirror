# 🪞 Smart Mirror

A clean, OLED-black smart mirror for Raspberry Pi — dual-screen rotating dashboard with sports scores, Strava walking stats, a daily selfie timeline, motion-activated sleep mode, and synced WLED lighting for selfie capture.

---

## Screens

**Screen 1 — Dashboard**
- Live clock + date
- NHL Panthers & NFL Cowboys game cards (only within 7 days, live scores when in-game)
- 3 selfie thumbnails: 1 month, 6 months, 1 year ago (gracefully empty if not yet taken)

**Screen 2 — Strava**
- YTD / recent / all-time walking stats (in miles)
- Full-year activity heatmap
- Recent walks list with distance & time

Screens auto-rotate every 60 seconds. The mirror sleeps (full black) when no motion is detected, and wakes instantly when you walk up.

---

## Project Structure

```
mirror/
├── public/
│   └── index.html          ← Full mirror UI (single-page)
├── server/
│   └── index.js            ← Express API server
├── scripts/
│   ├── capture.py          ← Webcam selfie + Immich upload
│   ├── button_listener.py  ← GPIO button daemon (gpiod)
│   ├── motion_sensor.py    ← HC-SR501 PIR daemon (gpiod)
│   ├── led_test.py         ← Standalone LED + button wiring test
│   └── strava-auth.js      ← One-time Strava token helper
├── .env.example             ← Config template
├── package.json
└── setup.sh                 ← One-shot Pi installer
```

---

## Setup

### 1. Clone to your Pi

```bash
git clone <your-repo> ~/mirror
cd ~/mirror
```

### 2. Configure credentials

```bash
cp .env.example .env
nano .env
```

Fill in:
- `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` / `STRAVA_REFRESH_TOKEN`
- `IMMICH_URL` / `IMMICH_API_KEY` / `IMMICH_ALBUM_ID`
- `WLED_URL` — your ESP32's IP address (e.g. `http://192.168.1.50`)
- `MOTION_GPIO_PIN` / `MOTION_GRACE_SECONDS` — defaults are fine for most setups

### 3. Get your Strava refresh token

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api) and create an app
2. Set Callback Domain to `localhost`
3. Visit this URL in your browser (replace `CLIENT_ID`):
   ```
   https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read,activity:read_all
   ```
4. Approve → copy the `code=` value from the redirect URL
5. Run:
   ```bash
   node scripts/strava-auth.js YOUR_CODE
   ```
6. Copy the printed `STRAVA_REFRESH_TOKEN` into `.env`

### 4. Set up Immich album

1. Create a new album in Immich named "Mirror Selfies"
2. Open the album — copy the UUID from the URL
3. Create an API key: Account Settings → API Keys
4. Add both to `.env`

### 5. Run setup

```bash
chmod +x setup.sh
bash setup.sh
sudo reboot
```

The mirror launches automatically in Chromium kiosk mode on boot.

---

## Physical Button (selfie capture)

Wire a momentary push button:
- One leg → **GPIO 18** (BCM, physical pin 12)
- Other leg → **GND**

Pressing it:
1. Shows a fullscreen black countdown (5 → 1), large numbers, "SMILE" label
2. WLED lights ramp from dim to full white brightness as the countdown approaches 0
3. Screen flashes white, photo is captured via webcam
4. Photo uploads to your Immich album
5. WLED lights restore to their default state/preset
6. Mirror resumes normal screen rotation

To change the GPIO pin, edit `BUTTON_PIN` in `scripts/button_listener.py`.

---

## Motion Sensor (HC-SR501, sleep/wake)

Wire the PIR sensor:
- **VCC** → Pi 5V (physical pin 2 or 4)
- **GND** → Pi GND (any ground pin)
- **OUT** → Pi **GPIO17** (physical pin 11) — or whatever you set `MOTION_GPIO_PIN` to in `.env`

The HC-SR501 has two onboard trimmer pots:
- **Sensitivity** — detection range (~3m to ~7m)
- **Time delay** — how long OUT stays HIGH after motion (~5s to ~300s)

Set the time delay trimmer to its **minimum** — the mirror handles the "how long to stay awake" logic in software via `MOTION_GRACE_SECONDS`, so you get one consistent, easily-tunable setting instead of fighting the sensor's own hardware delay. There's also a jumper for trigger mode; set it to **L** (single trigger) for cleaner detection.

The sensor daemon waits 30 seconds on boot for the PIR to stabilize (this is normal — HC-SR501 units are noisy for the first ~30-60s after power-up).

When no motion has been seen for `MOTION_GRACE_SECONDS` (default 45s), the screen fades to black. Any motion wakes it instantly.

---

## WLED Lighting (ESP32)

The mirror calls your existing WLED installation over its built-in JSON HTTP API — no changes needed to your ESP32 code.

- **During countdown**: `POST /api/lights/countdown` sends `{on: true, bri: <ramping 60→255>, seg:[{col:[[255,255,255]], fx:0}]}` to WLED, getting brighter each second
- **After capture**: `POST /api/lights/restore` recalls your default preset

To make "restore" return to your exact existing setup:
1. In the WLED web UI, save your current default look as a **Preset** (Presets tab → save current state)
2. Note its preset ID number
3. Set `WLED_DEFAULT_PRESET=<id>` in `.env`

If left blank, restore just sends `{on: true}`, which works fine for most static WLED setups but won't recall a specific saved effect/preset.

---

## Manual commands

```bash
# Start/stop services
sudo systemctl start mirror mirror-button mirror-motion
sudo systemctl stop mirror mirror-button mirror-motion

# View logs
journalctl -u mirror -f
journalctl -u mirror-button -f
journalctl -u mirror-motion -f

# Test capture manually
sudo python3 scripts/capture.py

# Test button + LED wiring
sudo python3 scripts/led_test.py

# Restart everything
sudo systemctl restart mirror mirror-button mirror-motion
```

---

## Customization

| What | Where |
|------|-------|
| Greeting name | `public/index.html` — search `Zach` |
| Rotation speed | `public/index.html` — `ROTATE_MS` |
| Teams tracked | `server/index.js` — `TEAMS` object |
| Button GPIO pin | `scripts/button_listener.py` — `BUTTON_PIN` |
| Motion GPIO pin | `.env` — `MOTION_GPIO_PIN` |
| Sleep grace period | `.env` — `MOTION_GRACE_SECONDS` |
| WLED address | `.env` — `WLED_URL` |
| WLED default preset | `.env` — `WLED_DEFAULT_PRESET` |
| Selfie milestones | `server/index.js` — `milestones` array |

---

## APIs Used

| Service | Auth | Cost |
|---------|------|------|
| ESPN (scores) | None | Free |
| Strava | OAuth2 | Free |
| Immich | API Key | Self-hosted |
| WLED | None (local network) | Self-hosted |
