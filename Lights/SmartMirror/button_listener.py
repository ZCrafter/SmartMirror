#!/usr/bin/env python3
"""
button_listener.py — Runs as a systemd service on the Pi.
Listens for a physical button press on GPIO pin 18,
then calls the mirror's /api/selfie/capture endpoint.
"""

import time
import requests

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print('RPi.GPIO not found — running in keyboard simulation mode')

BUTTON_PIN   = 18          # BCM pin number — wire button between pin 18 and GND
MIRROR_URL   = 'http://localhost:3000'
DEBOUNCE_MS  = 300

def on_button_press(channel):
    print('Button pressed — triggering capture...')
    try:
        resp = requests.post(f'{MIRROR_URL}/api/selfie/capture', timeout=15)
        print('Capture response:', resp.json())
    except Exception as e:
        print(f'Capture failed: {e}')

def main_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(
        BUTTON_PIN,
        GPIO.FALLING,
        callback=on_button_press,
        bouncetime=DEBOUNCE_MS,
    )
    print(f'Listening for button on GPIO {BUTTON_PIN}...')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        GPIO.cleanup()

def main_keyboard():
    """Fallback for development: press Enter to simulate button."""
    print('Press ENTER to simulate button press (Ctrl+C to quit)')
    try:
        while True:
            input()
            on_button_press(None)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    if HAS_GPIO:
        main_gpio()
    else:
        main_keyboard()
