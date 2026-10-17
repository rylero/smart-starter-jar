#!/usr/bin/env python3
"""Always-on collector: live site, light toggle, Influx samples, and timelapse frames."""

from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import light
import logger
from camera.server import AppState, LatestFrame, start_camera, start_frame_pump, start_http
from sensor.dht11 import read as read_dht11

SENSOR_INTERVAL = float(os.environ.get("SENSOR_INTERVAL", "60"))
FRAME_INTERVAL = float(os.environ.get("FRAME_INTERVAL", "900"))
STREAM_BIND = os.environ.get("STREAM_BIND", "0.0.0.0")
STREAM_PORT = int(os.environ.get("STREAM_PORT", "8080"))
STREAM_WIDTH = int(os.environ.get("STREAM_WIDTH", os.environ.get("FRAME_WIDTH", "1280")))
STREAM_HEIGHT = int(os.environ.get("STREAM_HEIGHT", os.environ.get("FRAME_HEIGHT", "720")))
STREAM_FPS = int(os.environ.get("STREAM_FPS", "8"))
STREAM_EV = os.environ.get("STREAM_EV", "1.5")
TIMELAPSE_DIR = Path(os.environ.get("TIMELAPSE_DIR", "data/timelapse")).resolve()
RPICAM_EXTRA_ARGS = [part for part in os.environ.get("RPICAM_EXTRA_ARGS", "").split() if part]


def camera_args() -> list[str]:
    extra = list(RPICAM_EXTRA_ARGS)
    if STREAM_EV and "--ev" not in extra:
        extra.extend(["--ev", STREAM_EV])
    return extra


def save_frame(frames: LatestFrame) -> Path:
    now = datetime.now(timezone.utc)
    day_dir = TIMELAPSE_DIR / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    dest = day_dir / f"{now.strftime('%H%M%S')}.jpg"

    was_on = light.is_on()
    if not was_on:
        light.set_light(True)
        time.sleep(0.4)
    try:
        previous = frames.get()
        frame = frames.wait(previous, timeout=3.0) or frames.get()
        if not frame:
            raise RuntimeError("no camera frame yet")
        dest.write_bytes(frame)
    finally:
        if not was_on:
            light.set_light(False)

    shutil.copyfile(dest, TIMELAPSE_DIR / "latest.jpg")
    return dest


def main() -> int:
    TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)
    light.set_light(False)

    frames = LatestFrame()
    state = AppState(frames)
    camera = None
    server = None
    try:
        camera = start_camera(STREAM_WIDTH, STREAM_HEIGHT, STREAM_FPS, camera_args())
        start_frame_pump(camera, frames)
        print("camera stream started", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"camera stream failed: {exc}", file=sys.stderr, flush=True)

    server = start_http(state, STREAM_BIND, STREAM_PORT)
    print(
        f"collector started sensor={SENSOR_INTERVAL}s frame={FRAME_INTERVAL}s "
        f"site=http://{STREAM_BIND}:{STREAM_PORT}/ light=GPIO{','.join(str(p) for p in light.LIGHT_GPIOS)} "
        f"influx={logger.INFLUX_HOST}/{logger.INFLUX_DATABASE}",
        flush=True,
    )

    now = time.monotonic()
    next_sensor = now
    next_frame = now
    last_frame_name: str | None = None

    try:
        while True:
            now = time.monotonic()
            if now >= next_frame:
                try:
                    path = save_frame(frames)
                    last_frame_name = str(path.relative_to(TIMELAPSE_DIR))
                    print(f"saved frame {last_frame_name}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"frame capture failed: {exc}", file=sys.stderr, flush=True)
                next_frame = now + FRAME_INTERVAL

            if now >= next_sensor:
                try:
                    temp_c, humidity = read_dht11()
                    state.set_reading(temp_c, humidity)
                    logger.log(temp_c, humidity, last_frame_name)
                    print(f"{temp_c:.1f} C  {humidity:.1f} %RH", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"sensor read failed: {exc}", file=sys.stderr, flush=True)
                next_sensor = now + SENSOR_INTERVAL

            time.sleep(1)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if camera is not None:
            camera.terminate()
        light.set_light(False)


if __name__ == "__main__":
    raise SystemExit(main())
