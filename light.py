"""GPIO capture lights."""

from __future__ import annotations

import os
import subprocess
import threading

def _pins() -> list[int]:
    raw = os.environ.get("LIGHT_GPIOS", os.environ.get("LIGHT_GPIO", "24"))
    return [int(part) for part in raw.replace(",", " ").split() if part]


LIGHT_GPIOS = _pins()
LIGHT_GPIO = LIGHT_GPIOS[0]

_lock = threading.Lock()
_on = False


def set_light(on: bool) -> bool:
    global _on
    level = "dh" if on else "dl"
    for gpio in LIGHT_GPIOS:
        subprocess.run(["pinctrl", "set", str(gpio), "op", level], check=True)
    with _lock:
        _on = bool(on)
        return _on


def toggle() -> bool:
    return set_light(not is_on())


def is_on() -> bool:
    with _lock:
        return _on
