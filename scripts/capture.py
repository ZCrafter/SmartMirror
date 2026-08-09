#!/usr/bin/env python3
"""
capture.py — Captures from USB webcam (/dev/video0), uploads to Immich.
"""

import os
import sys
import datetime
import subprocess
import requests
import argparse
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

IMMICH_URL      = os.getenv('IMMICH_URL', 'http://192.168.200.119:2283')
IMMICH_API_KEY  = os.getenv('IMMICH_API_KEY', '')
IMMICH_ALBUM_ID = os.getenv('IMMICH_ALBUM_ID', '')

SAVE_DIR = ROOT / 'public' / 'selfies'
SAVE_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_SKIP_FRAMES = max(0, int(os.getenv('CAMERA_SKIP_FRAMES', '1')))
CAMERA_RESOLUTION = os.getenv('CAMERA_RESOLUTION', '1280x720')
CAMERA_JPEG_QUALITY = os.getenv('CAMERA_JPEG_QUALITY', '95')

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def capture_photo(delay_seconds: float = 0) -> Path:
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename  = SAVE_DIR / f'selfie_{timestamp}.jpg'
    log(f'Save path: {filename}')

    # Install fswebcam if missing
    check = subprocess.run(['which', 'fswebcam'], capture_output=True)
    if check.returncode != 0:
        log('fswebcam not found — installing...')
        subprocess.run(['apt-get', 'install', '-y', 'fswebcam'], check=True)

    # Try /dev/video0 first (USB webcam), then video1 as fallback
    for device in ['/dev/video0', '/dev/video1']:
        if not Path(device).exists():
            log(f'{device} not found, skipping')
            continue

        cmd = [
            'fswebcam',
            '-d', device,
            '-r', CAMERA_RESOLUTION,
            '--no-banner',
            '--skip', str(CAMERA_SKIP_FRAMES),
            '--jpeg', CAMERA_JPEG_QUALITY,
        ]
        # fswebcam opens and initializes the device before this delay. Starting
        # it during the on-screen countdown therefore gives auto-exposure time
        # to settle without adding dead time after zero.
        if delay_seconds > 0:
            cmd.extend(['--delay', str(int(round(delay_seconds)))])
        cmd.append(str(filename))
        log(f'Trying: {" ".join(cmd)}')
        result = subprocess.run(cmd, capture_output=True, text=True)
        log(f'  exit={result.returncode}')
        if result.stdout.strip():
            log(f'  stdout: {result.stdout.strip()}')
        if result.stderr.strip():
            log(f'  stderr: {result.stderr.strip()}')

        if result.returncode == 0 and filename.exists() and filename.stat().st_size > 1000:
            log(f'  SUCCESS — {filename.stat().st_size} bytes at {filename}')
            return filename

        if filename.exists():
            filename.unlink()
        log(f'  Failed on {device}')

    raise RuntimeError('Could not capture from any /dev/video device')

def upload_to_immich(filepath: Path) -> dict:
    if not IMMICH_API_KEY:
        log('IMMICH_API_KEY not set in .env — skipping upload')
        return {}
    if not IMMICH_ALBUM_ID:
        log('IMMICH_ALBUM_ID not set in .env — skipping upload')
        return {}

    log(f'Uploading to {IMMICH_URL}  album={IMMICH_ALBUM_ID}')
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
    if resp.status_code not in (200, 201):
        log(f'Upload error: {resp.text[:400]}')
        resp.raise_for_status()

    asset    = resp.json()
    asset_id = asset.get('id') or (asset[0].get('id') if isinstance(asset, list) else None)
    log(f'Asset ID: {asset_id}')

    resp2 = requests.put(
        f'{IMMICH_URL}/api/albums/{IMMICH_ALBUM_ID}/assets',
        headers={**headers, 'Content-Type': 'application/json'},
        json={'ids': [asset_id]},
        timeout=10,
    )
    log(f'Album add status: {resp2.status_code}')
    if resp2.status_code not in (200, 201):
        log(f'Album error: {resp2.text[:400]}')
    resp2.raise_for_status()
    log('Upload complete')
    return asset

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--delay',
        type=float,
        default=0,
        help='Seconds to keep the initialized camera open before capture',
    )
    args = parser.parse_args()

    log('capture.py starting')
    try:
        photo = capture_photo(max(0, args.delay))
        upload_to_immich(photo)
        log('Done')
    except Exception as e:
        log(f'ERROR: {e}')
        sys.exit(1)
