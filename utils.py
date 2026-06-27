from __future__ import annotations

from typing import Tuple

RGB = Tuple[int, int, int]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def clamp_int(value: float, minimum: int = 0, maximum: int = 255) -> int:
    return int(round(clamp(value, minimum, maximum)))


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def parse_rgb(value: str, default: RGB = (0, 0, 0)) -> RGB:
    try:
        parts = [int(p.strip()) for p in value.split(",")]
        if len(parts) != 3:
            return default
        return tuple(clamp_int(p) for p in parts)  # type: ignore[return-value]
    except Exception:
        return default


def parse_int_list(value: str, default: list[int] | None = None) -> list[int]:
    if default is None:
        default = []
    try:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    except Exception:
        return default


def scale_rgb(color: RGB, brightness: float) -> RGB:
    if brightness > 1:
        factor = clamp(brightness, 0, 255) / 255.0
    else:
        factor = clamp(brightness, 0, 1)
    return (
        clamp_int(color[0] * factor),
        clamp_int(color[1] * factor),
        clamp_int(color[2] * factor),
    )


def blend_rgb(a: RGB, b: RGB, amount: float) -> RGB:
    amount = clamp(amount, 0.0, 1.0)
    return (
        clamp_int(a[0] + (b[0] - a[0]) * amount),
        clamp_int(a[1] + (b[1] - a[1]) * amount),
        clamp_int(a[2] + (b[2] - a[2]) * amount),
    )


def overlay_rgb(base: RGB, top: RGB) -> RGB:
    return (
        clamp_int(base[0] + top[0]),
        clamp_int(base[1] + top[1]),
        clamp_int(base[2] + top[2]),
    )


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, "unknown", "unavailable", ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, "unknown", "unavailable", ""):
            return default
        return int(float(value))
    except Exception:
        return default


def format_rgb(color: RGB) -> str:
    return f"RGB({color[0]}, {color[1]}, {color[2]})"


def make_bar(value: float, maximum: float, width: int = 18, filled: str = "█", empty: str = "░") -> str:
    if maximum <= 0:
        count = 0
    else:
        count = int(round(clamp(value / maximum, 0, 1) * width))
    return filled * count + empty * (width - count)
