#!/usr/bin/env python3
"""
motion_sensor.py — Watches the HC-SR501 PIR motion sensor and notifies
the mirror server whenever motion is detected. Runs as a systemd daemon.

Wiring (HC-SR501):
  VCC  -> Pi 5V (pin 2 or 4)
  GND  -> Pi GND (any ground pin)
  OUT  -> Pi GPIO17 (physical pin 11)

The HC-SR501 has two onboard trimmers:
  - Sensitivity (left, usually) — detection range, ~3m to ~7m
  - Time delay (right, usually) — how long OUT stays HIGH after motion (~5s to ~300s)
Set the time delay low (its minimum, ~3-5s) since we handle the grace
period in software via MOTION_GRACE_SECONDS in .env — that gives us
one consistent, configurable place to tune "how long to stay awake."
There's also a jumper for trigger mode — set it to "L" (single trigger)
not "H" (repeatable trigger) for cleaner edge detection, though both work
with this script since we just watch the pin level.
"""

import time
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

PIR_PIN    = int(os.getenv('MOTION_GPIO_PIN', '17'))
MIRROR_URL = os.getenv('MIRROR_URL', 'http://localhost:3000')
POLL_S     = 0.5

def notify_motion():
    try:
        requests.post(f'{MIRROR_URL}/api/motion/event', json={'motion': True}, timeout=3)
    except Exception as e:
        log(f'Failed to notify mirror server: {e}')

def find_gpio_chip():
    import gpiod
    chips = sorted(Path('/dev').glob('gpiochip*'))
    log(f'Available chips: {[str(c) for c in chips]}')
    for c in chips:
        try:
            with gpiod.Chip(str(c)) as chip:
                info = chip.get_info()
                if info.num_lines > PIR_PIN:
                    log(f'Using {c} ({info.name}, {info.num_lines} lines)')
                    return str(c)
        except Exception as e:
            log(f'{c} error: {e}')
    raise RuntimeError(f'No gpiochip found with > {PIR_PIN} lines')

def main():
    import gpiod
    from gpiod.line import Bias, Direction, Value

    log('motion_sensor.py starting')
    log(f'PIR sensor on GPIO{PIR_PIN} — wiring: VCC->5V, GND->GND, OUT->GPIO{PIR_PIN}')

    chip_path = find_gpio_chip()

    with gpiod.request_lines(
        chip_path,
        consumer='motion-sensor',
        config={
            PIR_PIN: gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.PULL_DOWN,  # PIR OUT idles LOW, goes HIGH on motion
            )
        },
    ) as request:
        log('Allowing PIR sensor 30s warm-up time (HC-SR501 needs this on boot)...')
        time.sleep(30)
        log(f'Watching for motion on GPIO{PIR_PIN}...')

        last_state = Value.INACTIVE
        while True:
            value = request.get_value(PIR_PIN)
            if value == Value.ACTIVE and last_state == Value.INACTIVE:
                log('MOTION DETECTED')
                notify_motion()
            last_state = value
            time.sleep(POLL_S)

if __name__ == '__main__':
    main()
