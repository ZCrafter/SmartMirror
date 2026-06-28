from __future__ import annotations

import socket
from typing import List, Tuple

RGB = Tuple[int, int, int]

class WLED:
    """
    WLED DDP realtime sender. Use WLED_PORT=4048 in .env.
    Splits frames into safe DDP chunks.
    """
    def __init__(self, ip: str, port: int = 4048):
        self.ip = ip
        self.port = int(port)
        self.addr = (self.ip, self.port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.max_data_bytes = 480 * 3
        self.sequence = 0

    def send(self, pixels: List[RGB]) -> None:
        data = bytearray()
        for r, g, b in pixels:
            data.extend([self._byte(r), self._byte(g), self._byte(b)])
        offset = 0
        while offset < len(data):
            chunk = data[offset: offset + self.max_data_bytes]
            is_final = offset + self.max_data_bytes >= len(data)
            self._send_ddp_packet(chunk, offset=offset, push=is_final)
            offset += self.max_data_bytes
        self.sequence = (self.sequence + 1) % 256

    def off(self, count: int) -> None:
        self.send([(0, 0, 0)] * count)

    def _send_ddp_packet(self, data: bytearray, offset: int = 0, push: bool = True) -> None:
        length = len(data)
        flags = 0x40
        if push:
            flags |= 0x01
        header = bytearray([
            flags, self.sequence, 0x00, 0x01,
            (offset >> 24) & 0xFF,
            (offset >> 16) & 0xFF,
            (offset >> 8) & 0xFF,
            offset & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ])
        self.sock.sendto(header + data, self.addr)

    @staticmethod
    def _byte(value) -> int:
        try:
            value = int(value)
        except Exception:
            return 0
        return max(0, min(255, value))
