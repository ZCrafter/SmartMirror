from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_config
from renderer import map_frame_to_physical
from wled import WLED

def main() -> int:
    cfg = load_config()
    wled = WLED(cfg.WLED_IP, cfg.WLED_PORT)
    frame = [(0, 0, 0)] * cfg.TOTAL_LEDS
    for i in range(cfg.LEFT_START, cfg.LEFT_END + 1):
        frame[i] = cfg.LAYOUT_LEFT_COLOR
    for i in range(cfg.TOP_START, cfg.TOP_END + 1):
        frame[i] = cfg.LAYOUT_TOP_COLOR
    for i in range(cfg.RIGHT_START, cfg.RIGHT_END + 1):
        frame[i] = cfg.LAYOUT_RIGHT_COLOR
    print('Layout Test')
    print('Logical mirror layout:')
    print(f'Left  red   : {cfg.LEFT_START}-{cfg.LEFT_END}')
    print(f'Top   green : {cfg.TOP_START}-{cfg.TOP_END}')
    print(f'Right blue  : {cfg.RIGHT_START}-{cfg.RIGHT_END}')
    print(f'Strip reversed: {getattr(cfg, "STRIP_REVERSED", False)}')
    wled.send(map_frame_to_physical(frame, cfg))
    print('Frame sent.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
