import socket
import time

WLED_IP = "192.168.200.192"
WLED_PORT = 4048
TOTAL_LEDS = 554

data = bytearray()
for _ in range(TOTAL_LEDS):
    data.extend([255, 0, 0])

length = len(data)
offset = 0

header = bytearray([
    0x41,
    0x00,
    0x00,
    0x00,
    (offset >> 24) & 0xFF,
    (offset >> 16) & 0xFF,
    (offset >> 8) & 0xFF,
    offset & 0xFF,
    (length >> 8) & 0xFF,
    length & 0xFF,
])

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("Sending DDP red frames...")
for _ in range(60):
    sock.sendto(header + data, (WLED_IP, WLED_PORT))
    time.sleep(1 / 20)

print("Done.")
