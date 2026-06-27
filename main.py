from __future__ import annotations

import signal
import sys
import time

from animation import current_global_brightness, cycle_state, sleep_for_fps
from config import load_config
from debug import print_weather_debug
from renderer import blank_frame, render_weather_frame
from weather import WeatherClient
from wled import WLED


def fetch_weather_bundle(weather_client: WeatherClient) -> dict:
    current = weather_client.current()
    hourly = weather_client.hourly()
    daily = weather_client.daily()

    return {
        "current": current,
        "hourly": hourly,
        "daily": daily,
        "last_update": time.time(),
    }


def send_off_frame(cfg, wled: WLED) -> None:
    try:
        wled.send(blank_frame(cfg))
    except Exception:
        pass


def main() -> int:
    cfg = load_config()
    weather_client = WeatherClient(cfg)
    wled = WLED(cfg.WLED_IP, cfg.WLED_PORT)

    running = True

    def handle_shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("Starting Smart Mirror Weather LEDs")
    print(f"WLED: {cfg.WLED_IP}:{cfg.WLED_PORT}")
    print(f"Home Assistant: {cfg.HA_URL}")
    print(f"LEDs: total={cfg.TOTAL_LEDS}, left={cfg.LEFT_LEDS}, top={cfg.TOP_LEDS}, right={cfg.RIGHT_LEDS}")
    print()

    weather_bundle = None
    last_debug_print = 0.0

    while running:
        now = time.time()

        should_refresh = (
            weather_bundle is None
            or now - weather_bundle["last_update"] >= cfg.WEATHER_REFRESH_SECONDS
        )

        if should_refresh:
            try:
                weather_bundle = fetch_weather_bundle(weather_client)
                print("Weather refreshed.")
            except Exception as exc:
                print(f"Weather refresh failed: {exc}")

                if weather_bundle is None:
                    # Nothing useful to draw yet. Keep LEDs off and retry shortly.
                    send_off_frame(cfg, wled)
                    time.sleep(10)
                    continue

        anim = cycle_state(now, cfg)
        brightness = current_global_brightness(cfg)

        try:
            frame, meta = render_weather_frame(
                cfg=cfg,
                current_weather=weather_bundle["current"],
                hourly_forecast=weather_bundle["hourly"],
                daily_forecast=weather_bundle["daily"],
                comet_head_led=anim["head_led"],
                comet_fade_factor=anim["fade_factor"],
                global_brightness=brightness,
            )

            wled.send(frame)

            # Print full debug on weather refresh, then a lightweight status occasionally.
            if should_refresh or now - last_debug_print > cfg.WEATHER_REFRESH_SECONDS:
                print_weather_debug(
                    current=weather_bundle["current"],
                    hourly=weather_bundle["hourly"],
                    daily=weather_bundle["daily"],
                    meta=meta,
                    cfg=cfg,
                )
                last_debug_print = now
            else:
                print(
                    f"Comet LED={anim['head_led']:03d} "
                    f"paused={anim['paused']} "
                    f"fade={anim['fade_factor']:.2f} "
                    f"brightness={brightness}",
                    end="\r",
                )

        except Exception as exc:
            print(f"Render/send error: {exc}")

        sleep_for_fps(cfg)

    print()
    print("Stopping Smart Mirror Weather LEDs")
    send_off_frame(cfg, wled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
