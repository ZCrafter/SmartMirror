from __future__ import annotations

import signal
import time
import os
from pathlib import Path

from animation import current_global_brightness, cycle_state, sleep_for_fps
from config import load_config
from debug import print_weather_debug
from display_schedule import DisplaySchedule
from renderer import map_frame_to_physical, render_weather_frame
from weather import WeatherClient
from wled import WLED

def fetch_weather_bundle(weather_client: WeatherClient) -> dict:
    return {
        'current': weather_client.current(),
        'hourly': weather_client.hourly(),
        'daily': weather_client.daily(),
        'last_update': time.time(),
    }

def send_off_frame(cfg, wled: WLED) -> None:
    try:
        # BACKGROUND_COLOR belongs to the active weather glyph and may be a
        # visible white glow. Schedule-off needs its own explicit color.
        wled.send([cfg.SCHEDULE_OFF_COLOR] * cfg.TOTAL_LEDS)
    except Exception as exc:
        print(f'Failed to send schedule-off frame: {exc}', flush=True)

def main() -> int:
    cfg = load_config()
    display_schedule = DisplaySchedule()
    weather_client = WeatherClient(cfg)
    wled = WLED(cfg.WLED_IP, cfg.WLED_PORT)
    running = True
    lighting_override_lock = Path(
        os.getenv('LIGHTING_OVERRIDE_LOCK', '/run/smart-mirror-selfie-lighting.lock')
    )

    def handle_shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print('Starting Smart Mirror Weather LEDs')
    print(f'WLED: {cfg.WLED_IP}:{cfg.WLED_PORT}')
    print(f'Home Assistant: {cfg.HA_URL}')
    print(f'LEDs: total={cfg.TOTAL_LEDS}, left={cfg.LEFT_LEDS}, top={cfg.TOP_LEDS}, right={cfg.RIGHT_LEDS}')
    print(f'Strip reversed: {getattr(cfg, "STRIP_REVERSED", False)}')
    print(f'Display control: {display_schedule.describe()}')

    weather_bundle = None
    last_debug_print = 0.0
    last_schedule_active = None

    while running:
        now = time.time()

        # Yield WLED ownership during a selfie even when the normal schedule is
        # off. The button can therefore still run a manual capture after hours.
        if lighting_override_lock.exists():
            sleep_for_fps(cfg)
            continue

        schedule_active = display_schedule.is_active()
        if schedule_active != last_schedule_active:
            print(
                'Lighting schedule is ACTIVE; weather LEDs enabled.'
                if schedule_active
                else 'Lighting schedule is INACTIVE; holding LEDs black.'
            )
            last_schedule_active = schedule_active

        if not schedule_active:
            # WLED can fall back to its saved yellow preset after DDP realtime
            # times out. Refreshing a black frame once per second keeps it dark.
            send_off_frame(cfg, wled)
            time.sleep(1)
            continue

        should_refresh = weather_bundle is None or now - weather_bundle['last_update'] >= cfg.WEATHER_REFRESH_SECONDS
        if should_refresh:
            try:
                weather_bundle = fetch_weather_bundle(weather_client)
                print('Weather refreshed.')
            except Exception as exc:
                print(f'Weather refresh failed: {exc}')
                if weather_bundle is None:
                    send_off_frame(cfg, wled)
                    time.sleep(10)
                    continue

        anim = cycle_state(now, cfg)
        brightness = current_global_brightness(cfg)

        try:
            logical_frame, meta = render_weather_frame(
                cfg=cfg,
                current_weather=weather_bundle['current'],
                hourly_forecast=weather_bundle['hourly'],
                daily_forecast=weather_bundle['daily'],
                comet_head_led=anim['head_led'],
                comet_fade_factor=anim['fade_factor'],
                global_brightness=brightness,
            )
            wled.send(map_frame_to_physical(logical_frame, cfg))
            if should_refresh or now - last_debug_print > cfg.WEATHER_REFRESH_SECONDS:
                print_weather_debug(weather_bundle['current'], weather_bundle['hourly'], weather_bundle['daily'], meta, cfg)
                last_debug_print = now
            else:
                print(f"Comet logical LED={anim['head_led']:03d} paused={anim['paused']} fade={anim['fade_factor']:.2f} brightness={brightness}", end='\r')
        except Exception as exc:
            print(f'Render/send error: {exc}')
        sleep_for_fps(cfg)

    print('\nStopping Smart Mirror Weather LEDs')
    send_off_frame(cfg, wled)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
