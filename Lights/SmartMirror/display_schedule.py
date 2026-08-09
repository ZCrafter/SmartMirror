"""Shared .env schedule handling for the weather LED process.

The Node server independently applies the same settings to the kiosk page.
Keeping this check local means the LEDs still follow the schedule if the
browser or Node server is temporarily unavailable.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV, override=False)

DAY_ALIASES = {
    "sun": "sun", "sunday": "sun",
    "mon": "mon", "monday": "mon",
    "tue": "tue", "tues": "tue", "tuesday": "tue",
    "wed": "wed", "wednesday": "wed",
    "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri",
    "sat": "sat", "saturday": "sat",
}
DAY_ORDER = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")


def _parse_days(value: str) -> set[str]:
    days: set[str] = set()
    for part in value.split(","):
        setting = part.strip().lower()
        if not setting:
            continue
        if setting not in DAY_ALIASES:
            raise ValueError(f"Unknown day in SCHEDULE_DAYS: {part.strip()}")
        days.add(DAY_ALIASES[setting])
    return days


def _parse_time(
    value: str, setting_name: str, allow_end_of_day: bool = False
) -> int:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"{setting_name} must use 24-hour HH:MM format")
    hours, minutes = (int(part) for part in parts)
    if allow_end_of_day and hours == 24 and minutes == 0:
        return 24 * 60
    if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
        raise ValueError(f"{setting_name} is outside the valid 00:00-23:59 range")
    return hours * 60 + minutes


def _parse_daily_windows(value: str, setting_name: str) -> list[tuple[int, int]]:
    normalized = value.strip().lower()
    if not normalized or normalized in {"off", "none"}:
        return []
    if normalized in {"all-day", "allday", "always"}:
        return [(0, 24 * 60)]

    windows: list[tuple[int, int]] = []
    for index, window_text in enumerate(normalized.split(","), start=1):
        parts = [part.strip() for part in window_text.strip().split("-")]
        if len(parts) != 2:
            raise ValueError(
                f"{setting_name} window {index} must look like 05:00-09:00"
            )
        start = _parse_time(parts[0], f"{setting_name} start")
        end = _parse_time(parts[1], f"{setting_name} end", allow_end_of_day=True)
        if start >= end:
            raise ValueError(
                f"{setting_name} window {window_text.strip()} must end after it "
                "starts; split overnight hours across two days"
            )
        windows.append((start, end))
    return sorted(windows)


def _format_minutes(minutes: int) -> str:
    if minutes == 24 * 60:
        return "24:00"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _format_daily_windows(windows: list[tuple[int, int]]) -> str:
    if not windows:
        return "off"
    if windows == [(0, 24 * 60)]:
        return "all-day"
    return ",".join(
        f"{_format_minutes(start)}-{_format_minutes(end)}"
        for start, end in windows
    )


class DisplaySchedule:
    """Evaluate DISPLAY_MODE=schedule using the root project's .env file."""

    def __init__(self) -> None:
        self.mode = os.getenv("DISPLAY_MODE", "always").strip().lower()
        if self.mode not in {"always", "schedule", "motion"}:
            raise ValueError("DISPLAY_MODE must be always, schedule, or motion")

        self.timezone_name = os.getenv(
            "SCHEDULE_TIMEZONE", "America/New_York"
        ).strip()
        try:
            self.timezone = ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"Unknown SCHEDULE_TIMEZONE: {self.timezone_name}"
            ) from exc

        self.windows: dict[str, list[tuple[int, int]]] = {
            day: [] for day in DAY_ORDER
        }
        per_day_configured = any(
            f"SCHEDULE_{day.upper()}" in os.environ for day in DAY_ORDER
        )

        if per_day_configured:
            self.source = "per-day"
            for day in DAY_ORDER:
                setting_name = f"SCHEDULE_{day.upper()}"
                self.windows[day] = _parse_daily_windows(
                    os.getenv(setting_name, "off"), setting_name
                )
        else:
            # Backward compatibility with the v3 single-window schedule.
            self.source = "legacy"
            days = _parse_days(
                os.getenv("SCHEDULE_DAYS", "mon,tue,wed,thu,fri")
            )
            start = _parse_time(
                os.getenv("SCHEDULE_START", "05:00").strip(),
                "SCHEDULE_START",
            )
            end = _parse_time(
                os.getenv("SCHEDULE_END", "21:00").strip(),
                "SCHEDULE_END",
            )
            for day in days:
                if start == end:
                    self.windows[day].append((0, 24 * 60))
                elif start < end:
                    self.windows[day].append((start, end))
                else:
                    self.windows[day].append((start, 24 * 60))
                    next_day = DAY_ORDER[(DAY_ORDER.index(day) + 1) % len(DAY_ORDER)]
                    self.windows[next_day].append((0, end))

        self.schedule_text = {
            day: _format_daily_windows(self.windows[day]) for day in DAY_ORDER
        }

    def is_active(self, at: datetime | None = None) -> bool:
        # Motion mode continues to leave LED control unchanged, matching the
        # previous implementation. Schedule mode explicitly controls LEDs.
        if self.mode != "schedule":
            return True

        local = at.astimezone(self.timezone) if at else datetime.now(self.timezone)
        day = local.strftime("%a").lower()
        minute = local.hour * 60 + local.minute

        return any(
            start <= minute < end for start, end in self.windows[day]
        )

    def describe(self) -> str:
        schedule = "; ".join(
            f"{day}={self.schedule_text[day]}" for day in DAY_ORDER
        )
        return (
            f"mode={self.mode}, source={self.source}, "
            f"timezone={self.timezone_name}, {schedule}"
        )
