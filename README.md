# 🪞 Smart Mirror

A clean, OLED-black smart mirror for Raspberry Pi — dual-screen rotating dashboard with sports scores, Strava walking stats, and a daily selfie timeline.

---

## Screens

**Screen 1 — Dashboard**
- Live clock + date
- NHL Panthers & NFL Cowboys game cards (only within 7 days, live scores when in-game)
- 3 selfie thumbnails: 1 month, 6 months, 1 year ago (gracefully empty if not yet taken)

**Screen 2 — Strava**
- YTD / recent / all-time walking stats
- Full-year activity heatmap
- Recent walks list with distance & time

Screens auto-rotate every 60 seconds.

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
│   ├── button_listener.py  ← GPIO button daemon
│   └── strava-auth.js      ← One-time Strava token helper
├── .env.example            ← Config template
├── package.json
└── setup.sh                ← One-shot Pi installer
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

## Physical Button

Wire a momentary push button:
- One leg → **GPIO 18** (BCM)
- Other leg → **GND**

Pressing it triggers `capture.py` which:
1. Takes a photo via webcam (libcamera or fswebcam)
2. Uploads to your Immich album
3. Flashes the screen white as confirmation

To change the GPIO pin, edit `BUTTON_PIN` in `scripts/button_listener.py`.

---

## Manual commands

```bash
# Start/stop server
sudo systemctl start mirror
sudo systemctl stop mirror

# View logs
journalctl -u mirror -f
journalctl -u mirror-button -f

# Test capture manually
python3 scripts/capture.py

# Restart everything
sudo systemctl restart mirror mirror-button
```

---

## Customization

| What | Where |
|------|-------|
| Greeting name | `public/index.html` — search `Zach` |
| Rotation speed | `public/index.html` — `ROTATE_MS` |
| Teams tracked | `server/index.js` — `TEAMS` object |
| GPIO pin | `scripts/button_listener.py` — `BUTTON_PIN` |
| Selfie milestones | `server/index.js` — `milestones` array |

---

## APIs Used

| Service | Auth | Cost |
|---------|------|------|
| ESPN (scores) | None | Free |
| Strava | OAuth2 | Free |
| Immich | API Key | Self-hosted |
