from __future__ import annotations

from typing import List, Tuple

from utils import RGB, blend_rgb, clamp, scale_rgb


def color_from_gradient(value: float, stops: List[Tuple[float, RGB]]) -> RGB:
    if not stops:
        return (0, 0, 0)

    stops = sorted(stops, key=lambda x: x[0])

    if value <= stops[0][0]:
        return stops[0][1]
    if value >= stops[-1][0]:
        return stops[-1][1]

    for i in range(len(stops) - 1):
        left_value, left_color = stops[i]
        right_value, right_color = stops[i + 1]
        if left_value <= value <= right_value:
            span = right_value - left_value
            if span <= 0:
                return right_color
            return blend_rgb(left_color, right_color, (value - left_value) / span)

    return stops[-1][1]


def temperature_color(temp_f: float, cfg) -> RGB:
    stops = [
        (0, cfg.FREEZING_COLOR),
        (32, cfg.COLD_COLOR),
        (50, cfg.COOL_COLOR),
        (68, cfg.COMFORTABLE_COLOR),
        (78, cfg.WARM_COLOR),
        (90, cfg.HOT_COLOR),
        (100, cfg.VERY_HOT_COLOR),
    ]
    return color_from_gradient(temp_f, stops)


def humidity_color(humidity_percent: float, cfg) -> RGB:
    humidity_percent = clamp(humidity_percent, 0, 100)
    stops = [
        (0, cfg.HUMIDITY_0_COLOR),
        (20, cfg.HUMIDITY_20_COLOR),
        (40, cfg.HUMIDITY_40_COLOR),
        (60, cfg.HUMIDITY_60_COLOR),
        (80, cfg.HUMIDITY_80_COLOR),
        (100, cfg.HUMIDITY_100_COLOR),
    ]
    return color_from_gradient(humidity_percent, stops)


def precip_color(precip_inches: float, cfg) -> RGB:
    if precip_inches < cfg.PRECIP_MIN_VISIBLE_INCHES:
        return (0, 0, 0)

    span = max(0.001, cfg.PRECIP_FULL_BRIGHT_INCHES - cfg.PRECIP_MIN_VISIBLE_INCHES)
    normalized = clamp((precip_inches - cfg.PRECIP_MIN_VISIBLE_INCHES) / span, 0, 1)

    brightness = cfg.PRECIP_BRIGHTNESS_MIN + normalized * (
        cfg.PRECIP_BRIGHTNESS_MAX - cfg.PRECIP_BRIGHTNESS_MIN
    )

    return scale_rgb(cfg.RAIN_COLOR, brightness)
