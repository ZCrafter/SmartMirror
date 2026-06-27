from __future__ import annotations

import time
from datetime import datetime


def cycle_state(now: float, cfg) -> dict:
    """
    Return animation state for the current time.

    The comet travels from LED 0 to LED TOTAL_LEDS-1 over TRAVEL_TIME_SECONDS,
    pauses at the end, then restarts.
    """
    travel = max(0.1, float(cfg.TRAVEL_TIME_SECONDS))
    pause = max(0.0, float(cfg.PAUSE_TIME_SECONDS))
    cycle = travel + pause

    t = now % cycle

    if t <= travel:
        progress = t / travel
        paused = False
    else:
        progress = 1.0
        paused = True

    head_led = int(round(progress * (cfg.TOTAL_LEDS - 1)))

    fade_factor = 1.0

    # Optional fade-out near the very end of travel and throughout pause.
    if cfg.COMET_FADE_AT_END:
        fade_window = min(1.0, travel * 0.15)

        if not paused and t > travel - fade_window:
            fade_factor = max(0.0, (travel - t) / fade_window)
        elif paused:
            fade_factor = 0.0

    return {
        "now": now,
        "cycle_time": cycle,
        "cycle_position": t,
        "progress": progress,
        "head_led": head_led,
        "paused": paused,
        "fade_factor": fade_factor,
    }


def current_global_brightness(cfg, now_dt: datetime | None = None) -> int:
    """
    Return current global brightness, applying optional nighttime dimming.

    Night windows can cross midnight:
    NIGHT_START_HOUR=22
    NIGHT_END_HOUR=6
    means 10 PM through 6 AM.
    """
    if not cfg.ENABLE_NIGHT_DIMMING:
        return cfg.GLOBAL_BRIGHTNESS

    if now_dt is None:
        now_dt = datetime.now()

    hour = now_dt.hour
    start = cfg.NIGHT_START_HOUR
    end = cfg.NIGHT_END_HOUR

    if start == end:
        is_night = False
    elif start < end:
        is_night = start <= hour < end
    else:
        is_night = hour >= start or hour < end

    if is_night:
        return cfg.NIGHT_GLOBAL_BRIGHTNESS

    return cfg.GLOBAL_BRIGHTNESS


def sleep_for_fps(cfg) -> None:
    fps = max(1, int(cfg.FPS))
    time.sleep(1.0 / fps)
