from __future__ import annotations

from typing import List, Tuple

from colors import humidity_color, precip_color, temperature_color
from utils import RGB, clamp, overlay_rgb, scale_rgb

Frame = List[RGB]

def blank_frame(cfg) -> Frame:
    return [cfg.BACKGROUND_COLOR for _ in range(cfg.TOTAL_LEDS)]

def map_frame_to_physical(frame: Frame, cfg) -> Frame:
    if not getattr(cfg, 'STRIP_REVERSED', False):
        return frame
    physical = [(0, 0, 0)] * len(frame)
    for logical_index, color in enumerate(frame):
        physical[len(frame) - 1 - logical_index] = color
    return physical

def set_pixel(frame: Frame, index: int, color: RGB, additive: bool = True) -> None:
    if 0 <= index < len(frame):
        frame[index] = overlay_rgb(frame[index], color) if additive else color

def temp_to_vertical_offset(temp_f: float, cfg) -> int:
    span = cfg.MAX_TEMP_F - cfg.MIN_TEMP_F
    normalized = 0 if span <= 0 else (temp_f - cfg.MIN_TEMP_F) / span
    normalized = clamp(normalized, 0.0, 1.0)
    return int(round(normalized * (cfg.LEFT_LEDS - 1)))

def temp_to_left_led(temp_f: float, cfg) -> int:
    return cfg.LEFT_START + temp_to_vertical_offset(temp_f, cfg)

def temp_to_right_led(temp_f: float, cfg) -> int:
    offset = temp_to_vertical_offset(temp_f, cfg)
    return cfg.RIGHT_END - offset

def feels_like_color(actual_temp: float, feels_like: float, cfg) -> RGB:
    delta = feels_like - actual_temp
    scale = max(0.1, getattr(cfg, 'FEELS_DELTA_FULL_SCALE_F', 12.0))
    amount = clamp(abs(delta) / scale, 0.0, 1.0)
    if delta < -0.5:
        base = getattr(cfg, 'FEELS_COOLER_COLOR', (0, 170, 255))
    elif delta > 0.5:
        base = getattr(cfg, 'FEELS_WARMER_COLOR', (255, 90, 35))
    else:
        base = getattr(cfg, 'FEELS_SAME_COLOR', (160, 110, 255))
    min_brightness = cfg.FEELSLIKE_BRIGHTNESS * 0.55
    max_brightness = cfg.FEELSLIKE_BRIGHTNESS
    brightness = min_brightness + amount * (max_brightness - min_brightness)
    return scale_rgb(base, brightness)

def draw_daily_high_low(frame: Frame, daily_forecast: dict, cfg) -> dict:
    high = float(daily_forecast.get('temperature', 0))
    low = float(daily_forecast.get('templow', high))
    high_led = temp_to_left_led(high, cfg)
    low_led = temp_to_left_led(low, cfg)
    high_color = scale_rgb(cfg.HIGH_TEMP_COLOR, cfg.HIGH_TEMP_BRIGHTNESS)
    low_color = scale_rgb(cfg.LOW_TEMP_COLOR, cfg.LOW_TEMP_BRIGHTNESS)
    set_pixel(frame, low_led, low_color, additive=True)
    set_pixel(frame, high_led, high_color, additive=True)
    return {'high': high, 'low': low, 'high_led': high_led, 'low_led': low_led, 'high_color': high_color, 'low_color': low_color}

def draw_current_and_feels(frame: Frame, current_temp: float, feels_like: float, cfg) -> dict:
    current_led = temp_to_right_led(current_temp, cfg)
    feels_led = temp_to_right_led(feels_like, cfg)
    current_color = scale_rgb(temperature_color(current_temp, cfg), cfg.CURRENT_TEMP_BRIGHTNESS)
    feels_color = feels_like_color(current_temp, feels_like, cfg)
    set_pixel(frame, feels_led, feels_color, additive=True)
    set_pixel(frame, current_led, current_color, additive=True)
    return {'current_led': current_led, 'feels_led': feels_led, 'current_color': current_color, 'feels_color': feels_color, 'feels_delta': feels_like - current_temp}

def draw_precipitation(frame: Frame, hourly_forecast: list[dict], cfg) -> dict:
    hours = hourly_forecast[: cfg.PRECIP_HOURS]
    markers = []
    for hour_index, hour in enumerate(hours):
        precip = float(hour.get('precipitation', 0) or 0)
        led = cfg.TOP_START + int(round((hour_index + 0.5) * cfg.TOP_LEDS / cfg.PRECIP_HOURS))
        led = max(cfg.TOP_START, min(cfg.TOP_END, led))
        color = precip_color(precip, cfg)
        if color != (0, 0, 0):
            set_pixel(frame, led, color, additive=True)
            if precip >= cfg.PRECIP_FULL_BRIGHT_INCHES * 0.4:
                set_pixel(frame, led - 1, scale_rgb(color, 0.35), additive=True)
                set_pixel(frame, led + 1, scale_rgb(color, 0.35), additive=True)
        markers.append({'hour_index': hour_index, 'datetime': hour.get('datetime'), 'precipitation': precip, 'led': led, 'color': color})
    return {'markers': markers}

def draw_humidity_comet(frame: Frame, head_led: int, humidity: float, cfg, fade_factor: float = 1.0) -> dict:
    base_color = humidity_color(humidity, cfg)
    drawn = []
    tail_brightness = list(cfg.COMET_TAIL_BRIGHTNESS[: cfg.COMET_LENGTH])
    while len(tail_brightness) < cfg.COMET_LENGTH:
        previous = tail_brightness[-1] if tail_brightness else 255
        tail_brightness.append(max(3, int(previous * 0.45)))
    for tail_index in range(cfg.COMET_LENGTH):
        led = head_led - tail_index
        if led < 0:
            continue
        brightness = tail_brightness[tail_index] * (cfg.COMET_BRIGHTNESS / 255.0) * fade_factor
        color = scale_rgb(base_color, brightness)
        set_pixel(frame, led, color, additive=True)
        drawn.append({'tail_index': tail_index, 'led': led, 'brightness': int(brightness), 'color': color})
    return {'humidity': humidity, 'base_color': base_color, 'head_led': head_led, 'fade_factor': fade_factor, 'drawn': drawn}

def apply_global_brightness_to_frame(frame: Frame, brightness: int) -> Frame:
    return [scale_rgb(pixel, brightness) for pixel in frame]

def render_weather_frame(cfg, current_weather: dict, hourly_forecast: list[dict], daily_forecast: dict, comet_head_led: int, comet_fade_factor: float = 1.0, global_brightness: int | None = None) -> tuple[Frame, dict]:
    frame = blank_frame(cfg)
    meta = {}
    meta['left'] = draw_daily_high_low(frame, daily_forecast, cfg)
    meta['right'] = draw_current_and_feels(frame, current_weather['temp'], current_weather['feels'], cfg)
    meta['top'] = draw_precipitation(frame, hourly_forecast, cfg)
    meta['comet'] = draw_humidity_comet(frame, comet_head_led, current_weather['humidity'], cfg, comet_fade_factor)
    if global_brightness is None:
        global_brightness = cfg.GLOBAL_BRIGHTNESS
    frame = apply_global_brightness_to_frame(frame, global_brightness)
    meta['global_brightness'] = global_brightness
    return frame, meta
