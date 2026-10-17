"""GPIO capture light (BCM 24)."""

from __future__ import annotations

import os
import subprocess
import threading

LIGHT_GPIO = int(os.environ.get("LIGHT_GPIO", "24"))

_lock = threading.Lock()
_on = False


def set_light(on: bool) -> bool:
    global _on
    level = "dh" if on else "dl"
    subprocess.run(["pinctrl", "set", str(LIGHT_GPIO), "op", level], check=True)
    with _lock:
        _on = bool(on)
        return _on


def toggle() -> bool:
    return set_light(not is_on())


def is_on() -> bool:
    with _lock:
        return _on
