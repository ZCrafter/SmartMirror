from wled import WLED
import time

WLED_IP = "192.168.200.192"
TOTAL = 554

wled = WLED(WLED_IP, 4048)

red = [(255, 0, 0)] * TOTAL
green = [(0, 255, 0)] * TOTAL
blue = [(0, 0, 255)] * TOTAL
off = [(0, 0, 0)] * TOTAL

print("Sending red...")
for _ in range(40):
    wled.send(red)
    time.sleep(0.05)

print("Sending green...")
for _ in range(40):
    wled.send(green)
    time.sleep(0.05)

print("Sending blue...")
for _ in range(40):
    wled.send(blue)
    time.sleep(0.05)

print("Off...")
for _ in range(10):
    wled.send(off)
    time.sleep(0.05)
