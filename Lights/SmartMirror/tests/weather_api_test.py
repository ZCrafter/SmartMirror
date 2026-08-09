from __future__ import annotations

from config import load_config
from weather import WeatherClient


def main() -> int:
    cfg = load_config()
    wc = WeatherClient(cfg)

    print("Current:")
    print(wc.current())

    print()
    print("Daily:")
    print(wc.daily())

    print()
    print(f"Hourly first {cfg.PRECIP_HOURS}:")
    for h in wc.hourly()[: cfg.PRECIP_HOURS]:
        print(
            f"{h.get('datetime')}  "
            f"temp={h.get('temperature')}  "
            f"precip={h.get('precipitation')}  "
            f"humidity={h.get('humidity')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
