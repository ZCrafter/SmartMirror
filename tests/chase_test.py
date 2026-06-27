from __future__ import annotations

import time

from config import load_config
from wled import WLED


def main() -> int:
    cfg = load_config()
    wled = WLED(cfg.WLED_IP, cfg.WLED_PORT)

    delay = 0.02

    print("Chase Test")
    print("A white pixel will move from LED 0 to the final LED.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            for i in range(cfg.TOTAL_LEDS):
                frame = [(0, 0, 0)] * cfg.TOTAL_LEDS
                frame[i] = cfg.TEST_PIXEL_COLOR
                wled.send(frame)
                print(f"LED {i:03d}", end="\r")
                time.sleep(delay)
    except KeyboardInterrupt:
        wled.send([(0, 0, 0)] * cfg.TOTAL_LEDS)
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
