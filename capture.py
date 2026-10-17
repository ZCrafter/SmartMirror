#!/usr/bin/env python3
"""
capture.py — Triggered by the mirror button.
Takes a selfie via webcam, uploads it to Immich.
"""

import os
import sys
import time
import datetime
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

IMMICH_URL     = os.getenv('IMMICH_URL', 'http://192.168.200.119:2283')
IMMICH_API_KEY = os.getenv('IMMICH_API_KEY', '')
IMMICH_ALBUM_ID = os.getenv('IMMICH_ALBUM_ID', '')

SAVE_DIR = ROOT / 'public' / 'selfies'
SAVE_DIR.mkdir(parents=True, exist_ok=True)

def capture_photo() -> Path:
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename  = SAVE_DIR / f'selfie_{timestamp}.jpg'

    # USB webcam: fixed white balance + automatic exposure.
    # Skip initial frames so exposure can settle before saving.
    camera_controls = {
        'white_balance_automatic': 0,
        'white_balance_temperature': 6500,
        'auto_exposure': 0,
    }

    for control, value in camera_controls.items():
        subprocess.run(
            ['v4l2-ctl', '-d', '/dev/video0', '--set-ctrl', f'{control}={value}'],
            capture_output=True,
        )

    cmd_fswebcam = ['fswebcam', '-d', '/dev/video0', '--skip', '5', '-r', '1280x720', '--no-banner', str(filename)]

    result = subprocess.run(cmd_fswebcam, capture_output=True, text=True)
    print(f'fswebcam return code: {result.returncode}')
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0 and filename.exists():
        print(f'Captured: {filename}')
        return filename

    raise RuntimeError('fswebcam capture failed')

def upload_to_immich(filepath: Path) -> dict:
    if not IMMICH_API_KEY or not IMMICH_ALBUM_ID:
        print('Immich not configured — skipping upload')
        return {}

    headers = {'x-api-key': IMMICH_API_KEY}

    # 1. Upload asset
    with open(filepath, 'rb') as f:
        resp = requests.post(
            f'{IMMICH_URL}/api/assets',
            headers=headers,
            files={'assetData': (filepath.name, f, 'image/jpeg')},
            data={
                'deviceAssetId': filepath.name,
                'deviceId':      'smart-mirror',
                'fileCreatedAt': datetime.datetime.now().isoformat(),
                'fileModifiedAt': datetime.datetime.now().isoformat(),
            },
            timeout=30,
        )
    resp.raise_for_status()
    asset = resp.json()
    asset_id = asset.get('id') or asset[0].get('id')
    print(f'Uploaded asset: {asset_id}')

    # 2. Add to album
    resp2 = requests.put(
        f'{IMMICH_URL}/api/albums/{IMMICH_ALBUM_ID}/assets',
        headers={**headers, 'Content-Type': 'application/json'},
        json={'ids': [asset_id]},
        timeout=10,
    )
    resp2.raise_for_status()
    print(f'Added to album: {IMMICH_ALBUM_ID}')
    return asset

def blink_led(times=3):
    """Optional: blink GPIO LED to confirm capture. Silently skips if no GPIO."""
    try:
        import RPi.GPIO as GPIO
        LED_PIN = 17
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_PIN, GPIO.OUT)
        for _ in range(times):
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.15)
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.15)
        GPIO.cleanup()
    except Exception:
        pass

if __name__ == '__main__':
    try:
        photo = capture_photo()
        blink_led()
        upload_to_immich(photo)
        print('Done')
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
