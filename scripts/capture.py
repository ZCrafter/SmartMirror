#!/usr/bin/env python3
"""
capture.py — Captures from USB webcam (/dev/video0) using ffmpeg, uploads to Immich.
"""

import os
import sys
import datetime
import time
import subprocess
import requests
import argparse
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=True)

IMMICH_URL      = os.getenv('IMMICH_URL', 'http://192.168.200.119:2283')
IMMICH_API_KEY  = os.getenv('IMMICH_API_KEY', '')
IMMICH_ALBUM_ID = os.getenv('IMMICH_ALBUM_ID', '')

SAVE_DIR = ROOT / 'public' / 'selfies'
SAVE_DIR.mkdir(parents=True, exist_ok=True)

CAMERA_RESOLUTION = os.getenv('CAMERA_RESOLUTION', '1280x720')
CAMERA_FPS = os.getenv('CAMERA_FPS', '5')

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)
    try:
        open('/tmp/capture_last.log', 'a').write(f'[{ts}] {msg}\n')
    except Exception:
        pass

def capture_photo(delay_seconds: float = 0) -> Path:
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename  = SAVE_DIR / f'selfie_{timestamp}.jpg'
    log(f'Save path: {filename}')

    device = '/dev/video0'
    if not Path(device).exists():
        raise RuntimeError(f'{device} not found')

    exposure_time = int(os.getenv('CAMERA_EXPOSURE_TIME', '100'))
    log(f'Using CAMERA_EXPOSURE_TIME={exposure_time}, uid={os.getuid()}')
    base = (
        'auto_exposure=1,'
        f"brightness={int(os.getenv('CAMERA_BRIGHTNESS', '60'))},"
        f"contrast={int(os.getenv('CAMERA_CONTRAST', '32'))},"
        f"gamma={int(os.getenv('CAMERA_GAMMA', '220'))},"
        f"backlight_compensation={int(os.getenv('CAMERA_BACKLIGHT_COMPENSATION', '0'))},"
        f"saturation={int(os.getenv('CAMERA_SATURATION', '64'))},sharpness=8,"
        'white_balance_automatic=0,'
        f"white_balance_temperature={int(os.getenv('CAMERA_WHITE_BALANCE_TEMPERATURE', '6500'))},"
        'power_line_frequency=2'
    )

    def v4l(ctrl):
        subprocess.run(['v4l2-ctl', '-d', device, f'--set-ctrl={ctrl}'], capture_output=True, text=True)

    def read_exposure():
        r = subprocess.run(['v4l2-ctl', '-d', device, '--get-ctrl=exposure_time_absolute'], capture_output=True, text=True)
        try:
            return int(r.stdout.strip().split(':')[-1])
        except Exception:
            return None

    def shoot(path, skip):
        return subprocess.run(
            ['fswebcam', '-q', '-d', device, '--skip', str(skip), '-r', CAMERA_RESOLUTION, '--no-banner', str(path)],
            capture_output=True, text=True)

    v4l(base)
    v4l(f'exposure_time_absolute={exposure_time}')

    if delay_seconds > 0:
        log(f'Waiting {delay_seconds}s for lighting ramp...')
        time.sleep(delay_seconds)

    # Throwaway shot: the camera resets exposure on the first capture after controls change
    shoot('/tmp/wake.jpg', 3)

    for attempt in range(1, 5):
        v4l(f'exposure_time_absolute={exposure_time}')
        result = shoot(filename, 5)
        got = read_exposure()
        log(f'Attempt {attempt}: exposure {got}/{exposure_time} rc={result.returncode} exists={filename.exists()} stderr={result.stderr.strip()[:300]}')
        if result.returncode == 0 and filename.exists() and filename.stat().st_size > 1000 and got == exposure_time:
            log(f'SUCCESS - {filename.stat().st_size} bytes at {filename}')
            return filename

    if filename.exists() and filename.stat().st_size > 1000:
        log('WARNING: exposure readback never matched, using last frame anyway')
        return filename
    raise RuntimeError('Failed to capture frame via fswebcam')

def upload_to_immich(filepath: Path) -> dict:
    if not IMMICH_API_KEY or not IMMICH_ALBUM_ID:
        log('IMMICH_API_KEY or IMMICH_ALBUM_ID not set — skipping upload')
        return {}

    log(f'Uploading to {IMMICH_URL} album={IMMICH_ALBUM_ID}')
    headers = {'x-api-key': IMMICH_API_KEY}

    with open(filepath, 'rb') as f:
        resp = requests.post(
            f'{IMMICH_URL}/api/assets',
            headers=headers,
            files={'assetData': (filepath.name, f, 'image/jpeg')},
            data={
                'deviceAssetId':  filepath.name,
                'deviceId':       'smart-mirror',
                'fileCreatedAt':  datetime.datetime.now().isoformat(),
                'fileModifiedAt': datetime.datetime.now().isoformat(),
            },
            timeout=30,
        )
    log(f'Upload status: {resp.status_code}')
    resp.raise_for_status()

    asset = resp.json()
    asset_id = asset.get('id') or (asset[0].get('id') if isinstance(asset, list) else None)

    resp2 = requests.put(
        f'{IMMICH_URL}/api/albums/{IMMICH_ALBUM_ID}/assets',
        headers={**headers, 'Content-Type': 'application/json'},
        json={'ids': [asset_id]},
        timeout=10,
    )
    resp2.raise_for_status()
    log('Upload complete')
    return asset

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay', type=float, default=0)
    args = parser.parse_args()

    log('capture.py starting')
    try:
        photo = capture_photo(max(0, args.delay))
        upload_to_immich(photo)
        log('Done')
    except Exception as e:
        log(f'ERROR: {e}')
        sys.exit(1)
