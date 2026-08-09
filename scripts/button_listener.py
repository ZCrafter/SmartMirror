#!/usr/bin/env python3
"""
button_listener.py — gpiod v2 API (python3-gpiod on Pi OS Bookworm)
sudo apt install python3-gpiod gpiod
"""

import time
import datetime
import requests
from pathlib import Path

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

BUTTON_PIN = 18
MIRROR_URL = 'http://localhost:3000'
DEBOUNCE_S = 0.3

def blink_onboard_led(times=1):
    for led_name in ['led0', 'ACT', 'led1']:
        led_path     = Path(f'/sys/class/leds/{led_name}/brightness')
        trigger_path = Path(f'/sys/class/leds/{led_name}/trigger')
        if not led_path.exists():
            continue
        try:
            trigger_path.write_text('none')
            for _ in range(times):
                led_path.write_text('1')
                time.sleep(0.1)
                led_path.write_text('0')
                time.sleep(0.1)
            trigger_path.write_text('mmc0')
        except Exception as e:
            log(f'LED error: {e}')
        return

def trigger_capture_sequence():
    try:
        resp = requests.post(f'{MIRROR_URL}/api/selfie/trigger', timeout=5)
        log(f'Sequence response: {resp.status_code} {resp.text[:200]}')
    except requests.exceptions.ConnectionError:
        log('Connection refused — is mirror server running? sudo systemctl status mirror')
    except Exception as e:
        log(f'Request failed: {e}')

def main():
    import gpiod
    from gpiod.line import Bias, Edge

    log('button_listener.py starting (gpiod v2 API)')
    log(f'gpiod version: {gpiod.__version__}')

    # gpiochip4 is the main GPIO controller on Pi 5
    # gpiochip0 is correct for Pi 4 and earlier
    chips = sorted(Path('/dev').glob('gpiochip*'))
    log(f'Available chips: {[str(c) for c in chips]}')

    # Try chips in order, pick the one with enough lines for pin 18
    chip_path = None
    for c in chips:  # gpiochip0 is correct on Pi 4
        try:
            with gpiod.Chip(str(c)) as chip:
                info = chip.get_info()
                log(f'  {c}: {info.name}, {info.num_lines} lines')
                if info.num_lines > BUTTON_PIN:
                    chip_path = str(c)
                    log(f'  --> selected {c}')
                    break
        except Exception as e:
            log(f'  {c} error: {e}')

    if not chip_path:
        raise RuntimeError(f'No GPIO chip found with > {BUTTON_PIN} lines')

    log(f'Requesting GPIO{BUTTON_PIN} on {chip_path} with pull-up, falling edge...')

    with gpiod.request_lines(
        chip_path,
        consumer='mirror-button',
        config={
            BUTTON_PIN: gpiod.LineSettings(
                edge_detection=Edge.FALLING,
                bias=Bias.PULL_UP,
                debounce_period=datetime.timedelta(milliseconds=300),
            )
        },
    ) as request:
        log(f'Listening on GPIO{BUTTON_PIN} — press the button now')
        last_press = 0
        while True:
            # wait_edge_events blocks until an event or timeout
            if request.wait_edge_events(datetime.timedelta(seconds=1)):
                events = request.read_edge_events()
                for event in events:
                    now = time.time()
                    if now - last_press > DEBOUNCE_S:
                        last_press = now
                        log(f'BUTTON PRESSED (line={event.line_offset})')
                        blink_onboard_led(times=1)
                        trigger_capture_sequence()

if __name__ == '__main__':
    main()
