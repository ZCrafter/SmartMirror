# Smart Mirror

Raspberry Pi smart-mirror dashboard with scheduled weather LEDs/display, a
physical selfie button, optional HC-SR501 motion control, webcam capture,
Dreeve fitness data (with direct Strava fallback), and Immich upload.

This package contains one active copy of each component. The older duplicate
root files, nested Git repository, stale `Lights` prototype, `.env` credentials,
`node_modules`, cached Python files, and existing selfies are intentionally not
included.

## Runtime layout

```text
mirror/
├── server/index.js                 Node API and static-file server
├── public/index.html               Kiosk page
├── scripts/
│   ├── button_listener.py          GPIO18 selfie button
│   ├── motion_sensor.py            GPIO17 PIR daemon
│   ├── motion_debug.py             Continuous raw PIR diagnostic
│   ├── countdown_lights.py         Smooth warm-white selfie ramp
│   └── capture.py                  Webcam capture and Immich upload
└── Lights/SmartMirror/
    ├── main.py                     Weather animation loop
    ├── wled.py                     Chunked WLED DDP sender
    └── .env                        HA, WLED, layout, and lighting settings
```

Four systemd services own the long-running processes:

- `mirror.service`: Node server
- `mirror-lights.service`: weather LED animation
- `mirror-button.service`: physical button
- `mirror-motion.service`: PIR sensor

The weather animation must run through `mirror-lights.service`, not from a
terminal. During a selfie, the server tells that process to yield WLED output,
runs the white ramp, captures the photo, and then releases weather lighting.
This prevents two DDP senders from fighting over the strip.

## Upgrade an existing installation

Back up your two private configuration files before replacing the project:

```bash
cp ~/mirror/.env ~/mirror-root.env.backup
cp ~/mirror/Lights/SmartMirror/.env ~/mirror-lights.env.backup
```

Extract this package over `~/mirror`, then restore those `.env` files if your
extraction program replaced them. The package itself does not contain private
`.env` files.

Install dependencies and replace the old services:

```bash
cd ~/mirror
bash setup.sh
```

`setup.sh` stops an unmanaged weather process only when its command exactly
matches this project's weather `main.py`, installs the four services, and
restarts them.

Verify:

```bash
sudo systemctl status mirror mirror-lights mirror-button mirror-motion --no-pager
```

Only one weather process should appear:

```bash
pgrep -af 'Lights/SmartMirror/main.py'
```

## Selfie sequence

Pressing the GPIO18 button now calls `/api/selfie/trigger`. The kiosk page sees
the trigger and runs the same sequence as the `C` keyboard shortcut:

1. Pause weather DDP output while keeping its process and cached data alive.
2. Show the on-screen five-second countdown.
3. Ramp all LEDs smoothly at 30 FPS while the webcam opens and settles.
4. Capture at the end of the countdown and upload the photo.
5. Stop the white keepalive and immediately resume cached weather frames.

The webcam warm-up is configured in the root `.env`:

```dotenv
CAMERA_COUNTDOWN_DELAY_SECONDS=4
CAMERA_SKIP_FRAMES=1
CAMERA_RESOLUTION=1280x720
CAMERA_JPEG_QUALITY=95
```

`fswebcam` initializes the webcam first, then applies the configured delay.
Four seconds is intended to line the shot up with the end of the five-second
browser countdown on a Pi 2B. If a test photo is consistently early, increase
the delay to `5`; if it is consistently late, decrease it to `3`. The camera's
activity LED should turn on near the start of the countdown, not after zero.

Selfie white balance is configured in `Lights/SmartMirror/.env`:

```dotenv
COUNTDOWN_WHITE_RGB=255,190,120
COUNTDOWN_MIN_BRIGHTNESS=45
COUNTDOWN_FPS=30
```

If the light remains blue, reduce the final number. If it looks too orange,
increase it toward 255.

## Dreeve fitness data

Dreeve is the successor to Statistics for Strava. Merely running it at the old
URL and port does not redirect this mirror's old Strava API requests. Configure
the mirror to read Dreeve's generated activity table instead:

```dotenv
DREEVE_URL=http://YOUR_DREEVE_IP:PORT
DREEVE_ACTIVITIES_PATH=/api/activity/data-table.json
DREEVE_SPORT_TYPES=Walk
DREEVE_CACHE_SECONDS=300
```

Keep `DREEVE_URL` free of a trailing slash. If Dreeve is hosted under a path,
include that path in the URL, for example
`http://192.168.1.50:8080/dreeve`. The existing `STRAVA_*` settings are ignored
when `DREEVE_URL` is set, but may remain in `.env`.

Restart and test:

```bash
sudo systemctl restart mirror
curl -s http://localhost:3000/api/fitness/status
curl -s http://localhost:3000/api/strava/stats
curl -s http://localhost:3000/api/strava/activities | head -c 500
```

`/api/fitness/status` should report `"source":"dreeve"` and a nonzero
`matchingActivities` value. A zero count with no error usually means the
Dreeve sport type is not named `Walk`; add its exact type to the comma-separated
`DREEVE_SPORT_TYPES` setting. A 404 normally means the Dreeve base path is
missing from `DREEVE_URL`. A connection error means the Pi cannot reach that
host and port.

Dreeve's activity endpoint is generated data. Newly imported workouts will not
appear on the mirror until Dreeve has rebuilt its site/API output. The mirror
caches successful Dreeve reads for five minutes by default.

## Display and lighting schedule

The dashboard and weather LEDs can follow the same schedule. Outside the
schedule, the kiosk page is covered in black and the weather process sends the
configured `SCHEDULE_OFF_COLOR` once per second. The repeated frame matters
because WLED would otherwise leave realtime mode and return to its saved
preset.

Add these settings to the root `~/mirror/.env`:

```dotenv
DISPLAY_MODE=schedule
SCHEDULE_TIMEZONE=America/New_York
SCHEDULE_MON=05:00-21:00
SCHEDULE_TUE=05:00-21:00
SCHEDULE_WED=05:00-21:00
SCHEDULE_THU=05:00-21:00
SCHEDULE_FRI=05:00-21:00
SCHEDULE_SAT=07:00-12:00,17:00-22:00
SCHEDULE_SUN=07:00-21:00
```

Times use 24-hour `HH:MM` format. Each day may contain any number of
comma-separated windows. The Saturday example turns on twice: 7:00 AM-noon and
5:00-10:00 PM. An end time is the first inactive minute, so `05:00-21:00` is
active through 8:59 PM and turns off at 9:00 PM. The timezone name automatically
handles EST/EDT changes.

Use `off` to disable an entire day or `all-day` for a full day:

```dotenv
SCHEDULE_SUN=off
```

One window cannot cross midnight. Split it across the two affected days, such
as `20:00-24:00` on Monday and `00:00-02:00` on Tuesday. If any per-day setting
exists, the seven `SCHEDULE_MON` through `SCHEDULE_SUN` settings replace the old
`SCHEDULE_DAYS`, `SCHEDULE_START`, and `SCHEDULE_END` format.

After editing `.env`, restart both processes that read it:

```bash
sudo systemctl restart mirror mirror-lights
```

Check the server's decision:

```bash
curl -s http://localhost:3000/api/display/status
```

The JSON `active` value should be `true` inside the schedule and `false`
outside it. The physical selfie button remains available after hours: it
temporarily wakes the countdown/camera sequence and returns the dashboard and
LEDs to black afterward.

"Off" does not shut down the Raspberry Pi or remove power from the monitor.
The kiosk page becomes black and the lighting service sends recurring
schedule-off frames to WLED. The Pi, monitor electronics, browser, and services
keep running so the mirror can wake immediately at the next scheduled time.
Actual HDMI or monitor power control is a separate, display-server-specific
feature.

The schedule-off LED color is configured separately from the active glyph's
background in `~/mirror/Lights/SmartMirror/.env`:

```dotenv
SCHEDULE_OFF_COLOR=0,0,0
```

`0,0,0` is fully dark. A value such as `2,2,2` provides a very dim neutral
glow. This setting is deliberately separate from `BACKGROUND_COLOR`, which may
be visible while the weather glyph is active.

Other modes are available:

```dotenv
DISPLAY_MODE=always
```

keeps the dashboard and weather LEDs on continuously. `DISPLAY_MODE=motion`
uses the PIR for the dashboard while preserving the former LED behavior.

## Optional motion sensor

HC-SR501 wiring uses BCM numbering:

- VCC to Pi 5 V
- GND to Pi ground
- OUT to GPIO17, physical pin 11

The PIR dome must have an unobstructed view. Plexiglass and one-way mirror film
block the thermal infrared signal, so mount it below or beside the mirror.

The daemon logs HIGH/LOW transitions and sends a heartbeat every five seconds
while the PIR output stays HIGH. The server keeps the display awake for
`MOTION_GRACE_SECONDS` after the latest heartbeat.

The schedule is now the default. After mounting the sensor below the mirror,
switch the root `.env` to motion mode and restart the server:

```dotenv
DISPLAY_MODE=motion
```

```bash
sudo systemctl restart mirror mirror-motion
```

Live log:

```bash
sudo journalctl -u mirror-motion -f
```

Raw continuous test:

```bash
sudo systemctl stop mirror-motion
sudo python3 ~/mirror/scripts/motion_debug.py
sudo systemctl start mirror-motion
```

## Logs and manual tests

```bash
sudo journalctl -u mirror -f
sudo journalctl -u mirror-lights -f
sudo journalctl -u mirror-button -f
sudo journalctl -u mirror-motion -f
```

Trigger the complete browser sequence:

```bash
curl -X POST http://localhost:3000/api/selfie/trigger
```

Test only the smooth light ramp (stop weather first):

```bash
sudo systemctl stop mirror-lights
cd ~/mirror
SMART_MIRROR_DIR="$PWD/Lights/SmartMirror" python3 scripts/countdown_lights.py ramp 5
sudo systemctl start mirror-lights
```

## Configuration

- Root `.env`: server, Dreeve/Strava, Immich, camera, schedule, GPIO, and
  grace-period settings
- `Lights/SmartMirror/.env`: Home Assistant, WLED, LED layout, weather colors,
  animation timing, and selfie white balance

Start from the corresponding `.env.example` files on a new installation. Never
commit or share the real `.env` files because they contain access tokens.
