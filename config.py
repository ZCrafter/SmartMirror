from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

from utils import RGB, parse_bool, parse_int_list, parse_rgb

load_dotenv()


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    return parse_bool(os.getenv(name), default)


def env_rgb(name: str, default: RGB) -> RGB:
    return parse_rgb(os.getenv(name, ""), default)


@dataclass(frozen=True)
class Config:
    HA_URL: str
    HA_TOKEN: str
    ENTITY_TEMP: str
    ENTITY_FEELSLIKE: str
    ENTITY_HUMIDITY: str
    ENTITY_FORECAST: str

    WLED_IP: str
    WLED_PORT: int

    TOTAL_LEDS: int
    LEFT_LEDS: int
    TOP_LEDS: int
    RIGHT_LEDS: int

    FPS: int
    TRAVEL_TIME_SECONDS: float
    PAUSE_TIME_SECONDS: float
    WEATHER_REFRESH_SECONDS: int

    MIN_TEMP_F: float
    MAX_TEMP_F: float

    PRECIP_HOURS: int
    PRECIP_MIN_VISIBLE_INCHES: float
    PRECIP_FULL_BRIGHT_INCHES: float

    GLOBAL_BRIGHTNESS: int
    CURRENT_TEMP_BRIGHTNESS: int
    FEELSLIKE_BRIGHTNESS: int
    HIGH_TEMP_BRIGHTNESS: int
    LOW_TEMP_BRIGHTNESS: int
    PRECIP_BRIGHTNESS_MIN: int
    PRECIP_BRIGHTNESS_MAX: int
    COMET_BRIGHTNESS: int

    COMET_LENGTH: int
    COMET_TAIL_BRIGHTNESS: list[int]
    COMET_FADE_AT_END: bool

    ENABLE_NIGHT_DIMMING: bool
    NIGHT_START_HOUR: int
    NIGHT_END_HOUR: int
    NIGHT_GLOBAL_BRIGHTNESS: int

    FREEZING_COLOR: RGB
    COLD_COLOR: RGB
    COOL_COLOR: RGB
    COMFORTABLE_COLOR: RGB
    WARM_COLOR: RGB
    HOT_COLOR: RGB
    VERY_HOT_COLOR: RGB

    FEELSLIKE_COLOR: RGB
    HIGH_TEMP_COLOR: RGB
    LOW_TEMP_COLOR: RGB
    RAIN_COLOR: RGB

    HUMIDITY_0_COLOR: RGB
    HUMIDITY_20_COLOR: RGB
    HUMIDITY_40_COLOR: RGB
    HUMIDITY_60_COLOR: RGB
    HUMIDITY_80_COLOR: RGB
    HUMIDITY_100_COLOR: RGB

    BACKGROUND_COLOR: RGB

    LAYOUT_LEFT_COLOR: RGB
    LAYOUT_TOP_COLOR: RGB
    LAYOUT_RIGHT_COLOR: RGB
    TEST_PIXEL_COLOR: RGB

    @property
    def LEFT_START(self) -> int:
        return 0

    @property
    def LEFT_END(self) -> int:
        return self.LEFT_LEDS - 1

    @property
    def TOP_START(self) -> int:
        return self.LEFT_LEDS

    @property
    def TOP_END(self) -> int:
        return self.LEFT_LEDS + self.TOP_LEDS - 1

    @property
    def RIGHT_START(self) -> int:
        return self.LEFT_LEDS + self.TOP_LEDS

    @property
    def RIGHT_END(self) -> int:
        return self.TOTAL_LEDS - 1

    @property
    def PATH_LEDS(self) -> int:
        return self.LEFT_LEDS + self.TOP_LEDS + self.RIGHT_LEDS

    def validate(self) -> None:
        expected = self.LEFT_LEDS + self.TOP_LEDS + self.RIGHT_LEDS
        if expected != self.TOTAL_LEDS:
            raise ValueError(f"LED layout mismatch: LEFT+TOP+RIGHT={expected}, TOTAL_LEDS={self.TOTAL_LEDS}")
        if not self.HA_URL:
            raise ValueError("HA_URL is missing")
        if not self.HA_TOKEN:
            raise ValueError("HA_TOKEN is missing")
        if not self.WLED_IP:
            raise ValueError("WLED_IP is missing")
        if self.FPS <= 0:
            raise ValueError("FPS must be greater than 0")


def load_config() -> Config:
    cfg = Config(
        HA_URL=env_str("HA_URL", "http://homeassistant.local:8123"),
        HA_TOKEN=env_str("HA_TOKEN", ""),
        ENTITY_TEMP=env_str("ENTITY_TEMP", "sensor.openweathermap_temperature"),
        ENTITY_FEELSLIKE=env_str("ENTITY_FEELSLIKE", "sensor.openweathermap_feels_like_temperature"),
        ENTITY_HUMIDITY=env_str("ENTITY_HUMIDITY", "sensor.openweathermap_humidity"),
        ENTITY_FORECAST=env_str("ENTITY_FORECAST", "weather.forecast_home"),

        WLED_IP=env_str("WLED_IP", ""),
        WLED_PORT=env_int("WLED_PORT", 21324),

        TOTAL_LEDS=env_int("TOTAL_LEDS", 554),
        LEFT_LEDS=env_int("LEFT_LEDS", 217),
        TOP_LEDS=env_int("TOP_LEDS", 120),
        RIGHT_LEDS=env_int("RIGHT_LEDS", 217),

        FPS=env_int("FPS", 20),
        TRAVEL_TIME_SECONDS=env_float("TRAVEL_TIME_SECONDS", 10),
        PAUSE_TIME_SECONDS=env_float("PAUSE_TIME_SECONDS", 3),
        WEATHER_REFRESH_SECONDS=env_int("WEATHER_REFRESH_SECONDS", 300),

        MIN_TEMP_F=env_float("MIN_TEMP_F", 0),
        MAX_TEMP_F=env_float("MAX_TEMP_F", 100),

        PRECIP_HOURS=env_int("PRECIP_HOURS", 18),
        PRECIP_MIN_VISIBLE_INCHES=env_float("PRECIP_MIN_VISIBLE_INCHES", 0.01),
        PRECIP_FULL_BRIGHT_INCHES=env_float("PRECIP_FULL_BRIGHT_INCHES", 0.25),

        GLOBAL_BRIGHTNESS=env_int("GLOBAL_BRIGHTNESS", 255),
        CURRENT_TEMP_BRIGHTNESS=env_int("CURRENT_TEMP_BRIGHTNESS", 255),
        FEELSLIKE_BRIGHTNESS=env_int("FEELSLIKE_BRIGHTNESS", 80),
        HIGH_TEMP_BRIGHTNESS=env_int("HIGH_TEMP_BRIGHTNESS", 255),
        LOW_TEMP_BRIGHTNESS=env_int("LOW_TEMP_BRIGHTNESS", 255),
        PRECIP_BRIGHTNESS_MIN=env_int("PRECIP_BRIGHTNESS_MIN", 25),
        PRECIP_BRIGHTNESS_MAX=env_int("PRECIP_BRIGHTNESS_MAX", 180),
        COMET_BRIGHTNESS=env_int("COMET_BRIGHTNESS", 255),

        COMET_LENGTH=env_int("COMET_LENGTH", 6),
        COMET_TAIL_BRIGHTNESS=parse_int_list(env_str("COMET_TAIL_BRIGHTNESS", "255,160,90,45,20,8"), [255, 160, 90, 45, 20, 8]),
        COMET_FADE_AT_END=env_bool("COMET_FADE_AT_END", True),

        ENABLE_NIGHT_DIMMING=env_bool("ENABLE_NIGHT_DIMMING", False),
        NIGHT_START_HOUR=env_int("NIGHT_START_HOUR", 22),
        NIGHT_END_HOUR=env_int("NIGHT_END_HOUR", 6),
        NIGHT_GLOBAL_BRIGHTNESS=env_int("NIGHT_GLOBAL_BRIGHTNESS", 35),

        FREEZING_COLOR=env_rgb("FREEZING_COLOR", (0, 0, 255)),
        COLD_COLOR=env_rgb("COLD_COLOR", (0, 140, 255)),
        COOL_COLOR=env_rgb("COOL_COLOR", (0, 255, 255)),
        COMFORTABLE_COLOR=env_rgb("COMFORTABLE_COLOR", (0, 255, 80)),
        WARM_COLOR=env_rgb("WARM_COLOR", (255, 190, 0)),
        HOT_COLOR=env_rgb("HOT_COLOR", (255, 90, 0)),
        VERY_HOT_COLOR=env_rgb("VERY_HOT_COLOR", (255, 0, 0)),

        FEELSLIKE_COLOR=env_rgb("FEELSLIKE_COLOR", (180, 180, 180)),
        HIGH_TEMP_COLOR=env_rgb("HIGH_TEMP_COLOR", (255, 80, 0)),
        LOW_TEMP_COLOR=env_rgb("LOW_TEMP_COLOR", (0, 120, 255)),
        RAIN_COLOR=env_rgb("RAIN_COLOR", (0, 90, 255)),

        HUMIDITY_0_COLOR=env_rgb("HUMIDITY_0_COLOR", (150, 0, 255)),
        HUMIDITY_20_COLOR=env_rgb("HUMIDITY_20_COLOR", (0, 0, 255)),
        HUMIDITY_40_COLOR=env_rgb("HUMIDITY_40_COLOR", (0, 220, 255)),
        HUMIDITY_60_COLOR=env_rgb("HUMIDITY_60_COLOR", (0, 255, 80)),
        HUMIDITY_80_COLOR=env_rgb("HUMIDITY_80_COLOR", (255, 220, 0)),
        HUMIDITY_100_COLOR=env_rgb("HUMIDITY_100_COLOR", (255, 0, 0)),

        BACKGROUND_COLOR=env_rgb("BACKGROUND_COLOR", (0, 0, 0)),

        LAYOUT_LEFT_COLOR=env_rgb("LAYOUT_LEFT_COLOR", (255, 0, 0)),
        LAYOUT_TOP_COLOR=env_rgb("LAYOUT_TOP_COLOR", (0, 255, 0)),
        LAYOUT_RIGHT_COLOR=env_rgb("LAYOUT_RIGHT_COLOR", (0, 0, 255)),
        TEST_PIXEL_COLOR=env_rgb("TEST_PIXEL_COLOR", (255, 255, 255)),
    )
    cfg.validate()
    return cfg
