from __future__ import annotations

from datetime import datetime

from utils import format_rgb, make_bar


def print_weather_debug(current: dict, hourly: list[dict], daily: dict, meta: dict, cfg) -> None:
    """Print detailed weather and LED mapping debug information."""
    left = meta.get("left", {})
    right = meta.get("right", {})
    top = meta.get("top", {})
    comet = meta.get("comet", {})

    print()
    print("=" * 72)
    print(datetime.now().strftime("Smart Mirror Weather Debug  %Y-%m-%d %H:%M:%S"))
    print("-" * 72)

    print(f"Current Temp : {current.get('temp', 0):6.1f} °F")
    print(f"Feels Like   : {current.get('feels', 0):6.1f} °F")
    print(f"Humidity     : {current.get('humidity', 0):6.0f} %")
    print()

    print(f"Today's High : {right.get('high', 0):6.1f} °F  LED {right.get('high_led')}")
    print(f"Today's Low  : {right.get('low', 0):6.1f} °F  LED {right.get('low_led')}")
    print()

    print("Left Edge")
    print(f"  Current temp LED : {left.get('current_led')}  {format_rgb(left.get('current_color', (0,0,0)))}")
    print(f"  Feels-like LED   : {left.get('feels_led')}  {format_rgb(left.get('feels_color', (0,0,0)))}")
    print()

    print("Right Edge")
    print(f"  High LED         : {right.get('high_led')}  {format_rgb(right.get('high_color', (0,0,0)))}")
    print(f"  Low LED          : {right.get('low_led')}  {format_rgb(right.get('low_color', (0,0,0)))}")
    print()

    print("Humidity Comet")
    print(f"  Head LED         : {comet.get('head_led')}")
    print(f"  Base color       : {format_rgb(comet.get('base_color', (0,0,0)))}")
    print(f"  Fade factor      : {comet.get('fade_factor', 1.0):.2f}")
    print()

    print(f"Top Edge Precipitation: next {cfg.PRECIP_HOURS} hours")
    markers = top.get("markers", [])
    for m in markers[: cfg.PRECIP_HOURS]:
        precip = m.get("precipitation", 0)
        led = m.get("led")
        color = m.get("color", (0, 0, 0))
        dt = str(m.get("datetime", ""))[11:16]
        bar = make_bar(precip, cfg.PRECIP_FULL_BRIGHT_INCHES, width=12)
        visible = "ON " if color != (0, 0, 0) else "off"
        print(f"  {m.get('hour_index', 0)+1:02d} {dt}  {precip:5.2f} in  LED {led:3}  {visible} {bar}")

    print()
    print(ascii_mirror(meta, cfg))
    print("=" * 72)


def ascii_mirror(meta: dict, cfg) -> str:
    """
    Generate a compact ASCII visualization.

    This is not pixel-perfect; it is just to quickly confirm that markers
    are being placed in sensible regions.
    """
    height = 18
    width = 28

    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Frame outline
    for y in range(height):
        grid[y][0] = "│"
        grid[y][width - 1] = "│"
    for x in range(width):
        grid[0][x] = "─"

    grid[0][0] = "┌"
    grid[0][width - 1] = "┐"

    def left_y(led: int | None) -> int | None:
        if led is None:
            return None
        normalized = (led - cfg.LEFT_START) / max(1, cfg.LEFT_LEDS - 1)
        return height - 1 - int(round(normalized * (height - 1)))

    def right_y(led: int | None) -> int | None:
        if led is None:
            return None
        # Right is physically top-to-bottom.
        normalized = (led - cfg.RIGHT_START) / max(1, cfg.RIGHT_LEDS - 1)
        return int(round(normalized * (height - 1)))

    left = meta.get("left", {})
    right = meta.get("right", {})
    top = meta.get("top", {})
    comet = meta.get("comet", {})

    cy = None
    head = comet.get("head_led")
    if isinstance(head, int):
        if cfg.LEFT_START <= head <= cfg.LEFT_END:
            cy = left_y(head)
            if cy is not None:
                grid[cy][0] = "●"
        elif cfg.TOP_START <= head <= cfg.TOP_END:
            x = int(round((head - cfg.TOP_START) / max(1, cfg.TOP_LEDS - 1) * (width - 1)))
            grid[0][x] = "●"
        elif cfg.RIGHT_START <= head <= cfg.RIGHT_END:
            cy = right_y(head)
            if cy is not None:
                grid[cy][width - 1] = "●"

    y = left_y(left.get("current_led"))
    if y is not None:
        grid[y][0] = "T"

    y = left_y(left.get("feels_led"))
    if y is not None and grid[y][0] == "│":
        grid[y][0] = "F"

    y = right_y(right.get("high_led"))
    if y is not None:
        grid[y][width - 1] = "H"

    y = right_y(right.get("low_led"))
    if y is not None and grid[y][width - 1] == "│":
        grid[y][width - 1] = "L"

    for marker in top.get("markers", []):
        if marker.get("color") != (0, 0, 0):
            led = marker.get("led")
            if isinstance(led, int):
                x = int(round((led - cfg.TOP_START) / max(1, cfg.TOP_LEDS - 1) * (width - 1)))
                if grid[0][x] == "─":
                    grid[0][x] = "R"

    lines = ["".join(row) for row in grid]
    lines.append("")
    lines.append("Legend: T=current temp, F=feels-like, R=rain, H=high, L=low, ●=comet")
    return "\n".join(lines)
