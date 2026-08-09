#!/usr/bin/env python3
"""
ddp_debug_test.py — Standalone test that imports ddp.py DIRECTLY (the same
class main.py uses, unmodified) to rule out any difference in our
countdown_lights.py reimplementation. Sends solid white for 5 seconds.

Usage: python3 ddp_debug_test.py
"""
import sys
sys.path.insert(0, '/home/admin/mirror/Lights')

from ddp import DDP
import os
import time
from dotenv import load_dotenv

load_dotenv('/home/admin/mirror/Lights/.env')

WLED_IP    = os.getenv('WLED_IP')
WLED_PORT  = int(os.getenv('WLED_PORT', '4048'))
TOTAL_LEDS = int(os.getenv('TOTAL_LEDS', '566'))

print(f'Using ddp.py DIRECTLY -> {WLED_IP}:{WLED_PORT}, {TOTAL_LEDS} LEDs')

d = DDP(WLED_IP, WLED_PORT)
pixels = [(255, 255, 255)] * TOTAL_LEDS

print('Sending solid white for 5 seconds using the real ddp.py class...')
end = time.time() + 5
count = 0
while time.time() < end:
    d.send(pixels)
    count += 1
    time.sleep(0.05)
print(f'Done — sent {count} frames')
