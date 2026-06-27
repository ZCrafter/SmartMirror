from __future__ import annotations

from config import load_config
from wled import WLED


def main() -> int:
    cfg = load_config()
    wled = WLED(cfg.WLED_IP, cfg.WLED_PORT)

    frame = [(0, 0, 0)] * cfg.TOTAL_LEDS

    for i in range(0, cfg.TOTAL_LEDS, 10):
        frame[i] = cfg.TEST_PIXEL_COLOR

    # Make major section boundaries more obvious.
    for idx, color in [
        (cfg.LEFT_START, (255, 0, 0)),
        (cfg.LEFT_END, (255, 0, 0)),
        (cfg.TOP_START, (0, 255, 0)),
        (cfg.TOP_END, (0, 255, 0)),
        (cfg.RIGHT_START, (0, 0, 255)),
        (cfg.RIGHT_END, (0, 0, 255)),
    ]:
        if 0 <= idx < cfg.TOTAL_LEDS:
            frame[idx] = color

    print("Number Test")
    print("Every 10th LED is white.")
    print("Section endpoints are colored red/green/blue.")
    wled.send(frame)
    print("Frame sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
