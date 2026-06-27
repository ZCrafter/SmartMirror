# Smart Mirror Weather LEDs

A Raspberry Pi application that drives a single continuous WLED LED strip around a bedroom smart mirror. Weather data comes from Home Assistant, while the Raspberry Pi renders each frame and streams it to an ESP32 running WLED.

---

# Features

## Default Display

- Background LEDs off
- A moving "comet" starts at the bottom-left corner, travels:
  - Up the left side
  - Across the top
  - Down the right side
- The comet pauses briefly at the bottom-right before restarting.

The comet color represents the current humidity.

---

## Left Edge

Displays:

- Current temperature
- Feels-like temperature (lower brightness)

Temperature is mapped vertically.

Bottom = minimum configured temperature

Top = maximum configured temperature

---

## Top Edge

Displays the next 18 hourly forecasts.

Only hours with precipitation above the configured threshold are illuminated.

Brightness increases with precipitation amount.

---

## Right Edge

Displays:

- Today's forecast high
- Today's forecast low

---

# Hardware

- Raspberry Pi (tested with Raspberry Pi 2B)
- ESP32 running WLED 0.16+
- 554 WS2812 LEDs

Layout:

LED 0

↓

217 LEDs up left side

↓

120 LEDs across top

↓

217 LEDs down right side

↓

LED 553

There is no bottom edge.

---

# Project Structure

```
smart_mirror/
│
├── .env
├── .env.example
├── requirements.txt
│
├── config.py
├── utils.py
├── colors.py
├── weather.py
├── wled.py
├── renderer.py
├── animation.py
├── debug.py
├── main.py
│
├── tests/
│   ├── layout_test.py
│   ├── number_test.py
│   ├── chase_test.py
│   ├── weather_api_test.py
│   └── weather_render_test.py
│
└── systemd/
    └── smartmirror.service
```

---

# Home Assistant

Uses:

- sensor.openweathermap_temperature
- sensor.openweathermap_feels_like_temperature
- sensor.openweathermap_humidity
- weather.forecast_home

Current sensor values are read through the REST API.

Hourly and daily forecasts are retrieved using:

```
POST /api/services/weather/get_forecasts?return_response
```

---

# WLED

ESP32:

- GPIO 4
- 554 LEDs
- UDP Port 21324

---

# Installation

## 1. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure

```bash
cp .env.example .env
nano .env
```

Fill in:

- HA_URL
- HA_TOKEN
- WLED_IP

---

# Running

```bash
python main.py
```

---

# Debug/Test Programs

## Layout Test

```bash
python tests/layout_test.py
```

Displays:

- Left = Red
- Top = Green
- Right = Blue

Use this first to verify LED numbering.

---

## Number Test

```bash
python tests/number_test.py
```

Lights every 10th LED.

Useful for confirming indexing.

---

## Chase Test

```bash
python tests/chase_test.py
```

Moves one white LED across the strip.

Useful for finding:

- incorrect ordering
- skipped LEDs
- bad LEDs

---

## Weather API Test

```bash
python tests/weather_api_test.py
```

Prints:

- current weather
- daily forecast
- hourly forecast

---

## Weather Render Test

```bash
python tests/weather_render_test.py
```

Renders one complete frame and prints detailed debug information.

---

# Running as a Service

Copy the service file:

```bash
sudo cp systemd/smartmirror.service /etc/systemd/system/
```

Reload:

```bash
sudo systemctl daemon-reload
```

Enable:

```bash
sudo systemctl enable smartmirror.service
```

Start:

```bash
sudo systemctl start smartmirror.service
```

Logs:

```bash
journalctl -u smartmirror.service -f
```

---

# Configuration

Most behavior is controlled through `.env`.

Examples include:

- animation speed
- pause duration
- brightness
- night mode
- comet length
- comet fade
- precipitation thresholds
- color palette
- temperature range
- LED layout

No source code changes should be required for normal tuning.

---

# Future Ideas

- Motion sensor wake-up animation
- Calendar reminders
- Home Assistant notifications
- Air quality indicator
- Package delivery indicator
- Sunrise alarm animation
- Sleep mode
- Moon phase display

---

# Security

Use a dedicated Home Assistant long-lived access token for this project.

If a token has ever been shared publicly or pasted into a conversation, revoke it and create a new one before storing it in `.env`.
