from __future__ import annotations

from animation import current_global_brightness
from config import load_config
from debug import print_weather_debug
from renderer import render_weather_frame
from weather import WeatherClient
from wled import WLED


def main() -> int:
    cfg = load_config()
    weather = WeatherClient(cfg)
    wled = WLED(cfg.WLED_IP, cfg.WLED_PORT)

    current = weather.current()
    hourly = weather.hourly()
    daily = weather.daily()

    frame, meta = render_weather_frame(
        cfg=cfg,
        current_weather=current,
        hourly_forecast=hourly,
        daily_forecast=daily,
        comet_head_led=0,
        comet_fade_factor=1.0,
        global_brightness=current_global_brightness(cfg),
    )

    print_weather_debug(current, hourly, daily, meta, cfg)
    wled.send(frame)
    print("Static weather render sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
