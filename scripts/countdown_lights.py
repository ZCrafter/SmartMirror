#!/usr/bin/env python3
"""Drive the selfie light without competing with the weather renderer.

Usage:
    python3 countdown_lights.py ramp [duration_seconds]
    python3 countdown_lights.py <brightness_0_255>
    python3 countdown_lights.py off

The script imports the same chunked DDP sender and reads the same .env file as
the weather process. This avoids the oversized one-packet frames used by the
old countdown implementation.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIGHTS_DIR = Path(
    os.getenv("SMART_MIRROR_DIR", str(PROJECT_ROOT / "Lights" / "SmartMirror"))
).resolve()

load_dotenv(LIGHTS_DIR / ".env")
sys.path.insert(0, str(LIGHTS_DIR))

from utils import parse_rgb  # noqa: E402
from wled import WLED  # noqa: E402


WLED_IP = os.getenv("WLED_IP", "").strip()
WLED_PORT = int(os.getenv("WLED_PORT", "4048"))
TOTAL_LEDS = int(os.getenv("TOTAL_LEDS", "566"))
COUNTDOWN_FPS = max(5, int(os.getenv("COUNTDOWN_FPS", "30")))
COUNTDOWN_MIN_BRIGHTNESS = max(
    0, min(255, int(os.getenv("COUNTDOWN_MIN_BRIGHTNESS", "45")))
)
COUNTDOWN_WHITE_RGB = parse_rgb(
    os.getenv("COUNTDOWN_WHITE_RGB", "255,190,120"),
    (255, 190, 120),
)


def scale_color(color: tuple[int, int, int], brightness: float) -> tuple[int, int, int]:
    factor = max(0.0, min(255.0, brightness)) / 255.0
    return tuple(round(channel * factor) for channel in color)


def send_solid(wled: WLED, color: tuple[int, int, int]) -> None:
    wled.send([color] * TOTAL_LEDS)


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def run_ramp(wled: WLED, duration_seconds: float, hold_seconds: float = 0.0) -> None:
    duration_seconds = max(1.0, min(15.0, duration_seconds))
    frame_interval = 1.0 / COUNTDOWN_FPS
    started = time.monotonic()

    while True:
        elapsed = time.monotonic() - started
        progress = min(1.0, elapsed / duration_seconds)
        eased = smoothstep(progress)
        brightness = COUNTDOWN_MIN_BRIGHTNESS + (
            (255 - COUNTDOWN_MIN_BRIGHTNESS) * eased
        )
        send_solid(wled, scale_color(COUNTDOWN_WHITE_RGB, brightness))

        if progress >= 1.0:
            break
        time.sleep(frame_interval)

    print(
        f"Completed {duration_seconds:.1f}s ramp at {COUNTDOWN_FPS} FPS; "
        f"white={COUNTDOWN_WHITE_RGB}, LEDs={TOTAL_LEDS}"
    , flush=True)

    # Keep WLED in realtime mode at full white until the server finishes the
    # capture/upload and terminates this process. The time limit is a failsafe
    # in case the server disappears without cleaning up.
    hold_until = time.monotonic() + max(0.0, min(60.0, hold_seconds))
    final_color = scale_color(COUNTDOWN_WHITE_RGB, 255)
    while time.monotonic() < hold_until:
        send_solid(wled, final_color)
        time.sleep(0.1)


def main() -> int:
    if not WLED_IP:
        print(f"ERROR: WLED_IP not found in {LIGHTS_DIR / '.env'}", file=sys.stderr)
        return 1

    if len(sys.argv) < 2:
        print(
            "Usage: countdown_lights.py <ramp [seconds]|brightness_0_255|off>",
            file=sys.stderr,
        )
        return 1

    wled = WLED(WLED_IP, WLED_PORT)
    command = sys.argv[1].lower()

    if command == "off":
        send_solid(wled, (0, 0, 0))
        print(f"Sent OFF frame to {WLED_IP}:{WLED_PORT}")
        return 0

    if command == "ramp":
        duration = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
        hold_seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        run_ramp(wled, duration, hold_seconds)
        return 0

    try:
        brightness = max(0, min(255, int(command)))
    except ValueError:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1

    color = scale_color(COUNTDOWN_WHITE_RGB, brightness)
    end_time = time.monotonic() + 1.1
    while time.monotonic() < end_time:
        send_solid(wled, color)
        time.sleep(0.2)
    print(f"Held brightness {brightness}; white={COUNTDOWN_WHITE_RGB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
