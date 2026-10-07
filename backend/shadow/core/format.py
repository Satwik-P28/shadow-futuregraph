"""Display helpers. Clock formatting is used for any variable tagged unit=clock."""

from __future__ import annotations

from typing import Any


def format_value(unit: str, value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if unit == "clock" and isinstance(value, (int, float)):
        minutes = int(round(float(value)))
        hours, mins = divmod(minutes, 60)
        return f"{hours % 24}:{mins:02d}"
    if unit == "usd" and isinstance(value, (int, float)):
        number = float(value)
        sign = "+" if number > 0 else ""
        return f"{sign}${number:.0f}" if number.is_integer() else f"{sign}${number:.2f}"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    return str(value)
