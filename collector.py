#!/usr/bin/env python3
"""Log DHT11 samples to InfluxDB and save a CSI timelapse frame every 15 minutes."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import logger
from sensor.dht11 import read as read_dht11

SENSOR_INTERVAL = float(os.environ.get("SENSOR_INTERVAL", "60"))
FRAME_INTERVAL = float(os.environ.get("FRAME_INTERVAL", "900"))
FRAME_WIDTH = os.environ.get("FRAME_WIDTH", "1920")
FRAME_HEIGHT = os.environ.get("FRAME_HEIGHT", "1080")
LIGHT_GPIO = int(os.environ.get("LIGHT_GPIO", "24"))
TIMELAPSE_DIR = Path(os.environ.get("TIMELAPSE_DIR", "data/timelapse")).resolve()
RPICAM_EXTRA_ARGS = [part for part in os.environ.get("RPICAM_EXTRA_ARGS", "").split() if part]


def set_light(on: bool) -> None:
    level = "dh" if on else "dl"
    subprocess.run(["pinctrl", "set", str(LIGHT_GPIO), "op", level], check=True)


def capture_frame() -> Path:
    now = datetime.now(timezone.utc)
    day_dir = TIMELAPSE_DIR / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    dest = day_dir / f"{now.strftime('%H%M%S')}.jpg"
    rpicam = shutil.which("rpicam-still")
    if not rpicam:
        raise RuntimeError("rpicam-still not found")

    cmd = [
        rpicam,
        "--nopreview",
        "--timeout",
        "1000",
        "--width",
        FRAME_WIDTH,
        "--height",
        FRAME_HEIGHT,
        "--output",
        str(dest),
        *RPICAM_EXTRA_ARGS,
    ]
    set_light(True)
    try:
        time.sleep(0.15)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        set_light(False)
    latest = TIMELAPSE_DIR / "latest.jpg"
    shutil.copyfile(dest, latest)
    return dest


def main() -> int:
    TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)
    set_light(False)
    print(
        f"collector started sensor={SENSOR_INTERVAL}s frame={FRAME_INTERVAL}s "
        f"timelapse={TIMELAPSE_DIR} light=GPIO{LIGHT_GPIO} "
        f"influx={logger.INFLUX_HOST}/{logger.INFLUX_DATABASE}",
        flush=True,
    )

    now = time.monotonic()
    next_sensor = now
    next_frame = now
    last_frame_name: str | None = None

    while True:
        now = time.monotonic()

        if now >= next_frame:
            try:
                path = capture_frame()
                last_frame_name = str(path.relative_to(TIMELAPSE_DIR))
                print(f"saved frame {last_frame_name}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"frame capture failed: {exc}", file=sys.stderr, flush=True)
            next_frame = now + FRAME_INTERVAL

        if now >= next_sensor:
            try:
                temp_c, humidity = read_dht11()
                logger.log(temp_c, humidity, last_frame_name)
                print(f"{temp_c:.1f} C  {humidity:.1f} %RH", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"sensor read failed: {exc}", file=sys.stderr, flush=True)
            next_sensor = now + SENSOR_INTERVAL

        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
