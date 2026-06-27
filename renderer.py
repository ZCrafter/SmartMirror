from __future__ import annotations

from typing import List, Tuple

from colors import humidity_color, precip_color, temperature_color
from utils import RGB, clamp, overlay_rgb, scale_rgb


Frame = List[RGB]


def blank_frame(cfg) -> Frame:
    """Create a framebuffer filled with the configured background color."""
    return [cfg.BACKGROUND_COLOR for _ in range(cfg.TOTAL_LEDS)]


def set_pixel(frame: Frame, index: int, color: RGB, additive: bool = True) -> None:
    """Set or overlay a pixel if index is valid."""
    if index < 0 or index >= len(frame):
        return

    if additive:
        frame[index] = overlay_rgb(frame[index], color)
    else:
        frame[index] = color


def temp_to_vertical_offset(temp_f: float, cfg) -> int:
    """
    Convert a temperature to a vertical LED offset.

    0 = bottom
    LEFT_LEDS - 1 or RIGHT_LEDS - 1 = top
    """
    span = cfg.MAX_TEMP_F - cfg.MIN_TEMP_F
    if span <= 0:
        normalized = 0
    else:
        normalized = (temp_f - cfg.MIN_TEMP_F) / span

    normalized = clamp(normalized, 0.0, 1.0)
    return int(round(normalized * (cfg.LEFT_LEDS - 1)))


def temp_to_left_led(temp_f: float, cfg) -> int:
    """Map temperature to left edge LED index."""
    return cfg.LEFT_START + temp_to_vertical_offset(temp_f, cfg)


def temp_to_right_led(temp_f: float, cfg) -> int:
    """
    Map temperature to right edge LED index.

    Right strip direction is top-to-bottom:
    RIGHT_START = top-right
    RIGHT_END = bottom-right

    Since temperature scale is bottom-to-top, higher temps should appear
    closer to RIGHT_START.
    """
    offset = temp_to_vertical_offset(temp_f, cfg)
    return cfg.RIGHT_END - offset


def path_position_to_led(path_pos: int, cfg) -> int:
    """
    Convert path position to LED index.

    The physical LED path already matches:
    left bottom->top, top left->right, right top->bottom.

    So path position is the same as LED index for this layout.
    """
    return max(0, min(cfg.TOTAL_LEDS - 1, path_pos))


def draw_current_and_feels(frame: Frame, current_temp: float, feels_like: float, cfg) -> dict:
    """Draw current and feels-like temp markers on the left edge."""
    current_led = temp_to_left_led(current_temp, cfg)
    feels_led = temp_to_left_led(feels_like, cfg)

    current_color = scale_rgb(
        temperature_color(current_temp, cfg),
        cfg.CURRENT_TEMP_BRIGHTNESS,
    )

    feels_color = scale_rgb(
        cfg.FEELSLIKE_COLOR,
        cfg.FEELSLIKE_BRIGHTNESS,
    )

    # Draw feels first so current temp can be visually dominant if they overlap.
    set_pixel(frame, feels_led, feels_color, additive=True)
    set_pixel(frame, current_led, current_color, additive=True)

    return {
        "current_led": current_led,
        "feels_led": feels_led,
        "current_color": current_color,
        "feels_color": feels_color,
    }


def draw_daily_high_low(frame: Frame, daily_forecast: dict, cfg) -> dict:
    """Draw daily high/low markers on the right edge."""
    high = float(daily_forecast.get("temperature", 0))
    low = float(daily_forecast.get("templow", high))

    high_led = temp_to_right_led(high, cfg)
    low_led = temp_to_right_led(low, cfg)

    high_color = scale_rgb(cfg.HIGH_TEMP_COLOR, cfg.HIGH_TEMP_BRIGHTNESS)
    low_color = scale_rgb(cfg.LOW_TEMP_COLOR, cfg.LOW_TEMP_BRIGHTNESS)

    set_pixel(frame, low_led, low_color, additive=True)
    set_pixel(frame, high_led, high_color, additive=True)

    return {
        "high": high,
        "low": low,
        "high_led": high_led,
        "low_led": low_led,
        "high_color": high_color,
        "low_color": low_color,
    }


def draw_precipitation(frame: Frame, hourly_forecast: list[dict], cfg) -> dict:
    """
    Draw next PRECIP_HOURS of precipitation on the top edge.

    Top side:
    TOP_START = first top LED
    TOP_END = last top LED

    Each forecast hour maps to a bucket on the top edge.
    If precipitation is zero or below threshold, that hour is left off.
    """
    hours = hourly_forecast[: cfg.PRECIP_HOURS]
    markers = []

    if not hours:
        return {"markers": markers}

    for hour_index, hour in enumerate(hours):
        precip = float(hour.get("precipitation", 0) or 0)

        bucket_center = cfg.TOP_START + int(
            round((hour_index + 0.5) * cfg.TOP_LEDS / cfg.PRECIP_HOURS)
        )

        bucket_center = max(cfg.TOP_START, min(cfg.TOP_END, bucket_center))

        color = precip_color(precip, cfg)

        if color != (0, 0, 0):
            set_pixel(frame, bucket_center, color, additive=True)

            # Very small halo for readability if there is meaningful rain.
            if precip >= cfg.PRECIP_FULL_BRIGHT_INCHES * 0.4:
                set_pixel(frame, bucket_center - 1, scale_rgb(color, 0.35), additive=True)
                set_pixel(frame, bucket_center + 1, scale_rgb(color, 0.35), additive=True)

        markers.append(
            {
                "hour_index": hour_index,
                "datetime": hour.get("datetime"),
                "precipitation": precip,
                "led": bucket_center,
                "color": color,
            }
        )

    return {"markers": markers}


def draw_humidity_comet(frame: Frame, head_led: int, humidity: float, cfg, fade_factor: float = 1.0) -> dict:
    """
    Draw the moving humidity comet.

    The comet head is at head_led. Tail extends backward along the physical path.
    fade_factor is used near the end of the path for a polished fade-out.
    """
    base_color = humidity_color(humidity, cfg)
    drawn = []

    tail_brightness = cfg.COMET_TAIL_BRIGHTNESS[: cfg.COMET_LENGTH]

    # If the configured brightness list is too short, extend with gentle falloff.
    while len(tail_brightness) < cfg.COMET_LENGTH:
        previous = tail_brightness[-1] if tail_brightness else 255
        tail_brightness.append(max(3, int(previous * 0.45)))

    for tail_index in range(cfg.COMET_LENGTH):
        led = head_led - tail_index
        if led < 0:
            continue

        brightness = tail_brightness[tail_index]
        brightness = brightness * (cfg.COMET_BRIGHTNESS / 255.0) * fade_factor

        color = scale_rgb(base_color, brightness)
        set_pixel(frame, led, color, additive=True)

        drawn.append(
            {
                "tail_index": tail_index,
                "led": led,
                "brightness": int(brightness),
                "color": color,
            }
        )

    return {
        "humidity": humidity,
        "base_color": base_color,
        "head_led": head_led,
        "fade_factor": fade_factor,
        "drawn": drawn,
    }


def apply_global_brightness_to_frame(frame: Frame, brightness: int) -> Frame:
    """Apply global brightness to the entire frame."""
    return [scale_rgb(pixel, brightness) for pixel in frame]


def render_weather_frame(
    cfg,
    current_weather: dict,
    hourly_forecast: list[dict],
    daily_forecast: dict,
    comet_head_led: int,
    comet_fade_factor: float = 1.0,
    global_brightness: int | None = None,
) -> tuple[Frame, dict]:
    """
    Render one complete mirror frame and return:
    - framebuffer
    - metadata for debugging
    """
    frame = blank_frame(cfg)

    meta = {}

    meta["left"] = draw_current_and_feels(
        frame,
        current_weather["temp"],
        current_weather["feels"],
        cfg,
    )

    meta["right"] = draw_daily_high_low(
        frame,
        daily_forecast,
        cfg,
    )

    meta["top"] = draw_precipitation(
        frame,
        hourly_forecast,
        cfg,
    )

    meta["comet"] = draw_humidity_comet(
        frame,
        comet_head_led,
        current_weather["humidity"],
        cfg,
        comet_fade_factor,
    )

    if global_brightness is None:
        global_brightness = cfg.GLOBAL_BRIGHTNESS

    frame = apply_global_brightness_to_frame(frame, global_brightness)

    meta["global_brightness"] = global_brightness

    return frame, meta
