#!/usr/bin/env python3
"""
Sends a single bright red pixel at index 0, rest black — mimics a typical
main.py-style sparse frame instead of an all-white flood. Helps determine
if solid-white specifically is the problem, or any standalone send fails.
"""
import sys
sys.path.insert(0, '/home/admin/mirror/Lights')
from ddp import DDP
import time

d = DDP('192.168.200.192', 4048)
TOTAL = 554

pixels = [(0, 0, 0)] * TOTAL
pixels[0] = (255, 0, 0)
pixels[100] = (255, 0, 0)
pixels[300] = (255, 0, 0)
pixels[550] = (255, 0, 0)

print('Sending sparse red pixels (indices 0, 100, 300, 550) for 5 seconds...')
end = time.time() + 5
while time.time() < end:
    d.send(pixels)
    time.sleep(0.05)
print('done')
