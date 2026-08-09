#!/usr/bin/env python3
"""Continuously print the raw HC-SR501 state on the configured GPIO line.

Stop mirror-motion.service before running this utility so it can claim the
GPIO line. Press Ctrl+C to exit, then restart the service.
"""

import os
import time
from pathlib import Path

import gpiod
from dotenv import load_dotenv
from gpiod.line import Bias, Direction, Value


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

PIR_PIN = int(os.getenv('MOTION_GPIO_PIN', '17'))
POLL_S = float(os.getenv('MOTION_DEBUG_POLL_SECONDS', '0.25'))


def find_gpio_chip() -> str:
    for chip_path in sorted(Path('/dev').glob('gpiochip*')):
        try:
            with gpiod.Chip(str(chip_path)) as chip:
                if chip.get_info().num_lines > PIR_PIN:
                    return str(chip_path)
        except Exception:
            continue
    raise RuntimeError(f'No GPIO chip contains GPIO{PIR_PIN}')


def main() -> int:
    chip_path = find_gpio_chip()
    print(f'Reading GPIO{PIR_PIN} on {chip_path}; press Ctrl+C to stop.')

    with gpiod.request_lines(
        chip_path,
        consumer='mirror-motion-debug',
        config={
            PIR_PIN: gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.PULL_DOWN,
            )
        },
    ) as request:
        try:
            while True:
                value = request.get_value(PIR_PIN)
                label = 'MOTION / HIGH' if value == Value.ACTIVE else 'CLEAR / LOW'
                print(f"{time.strftime('%H:%M:%S')}  {label}", flush=True)
                time.sleep(POLL_S)
        except KeyboardInterrupt:
            print('\nMotion debug stopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
