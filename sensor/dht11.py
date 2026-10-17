#!/usr/bin/env python3
"""Read a DHT11 on BCM GPIO 17 using Adafruit CircuitPython."""

from __future__ import annotations

import argparse
import os
import sys
import time

DEFAULT_GPIO = 17


def open_sensor(gpio: int):
    import adafruit_dht
    import board

    pin = getattr(board, f"D{gpio}", None)
    if pin is None:
        raise SystemExit(f"board.D{gpio} is not a valid CircuitPython pin")
    return adafruit_dht.DHT11(pin, use_pulseio=False)


def read_once(sensor) -> tuple[float, float]:
    temperature = sensor.temperature
    humidity = sensor.humidity
    if temperature is None or humidity is None:
        raise RuntimeError("DHT11 returned an empty reading")
    return float(temperature), float(humidity)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpio", type=int, default=int(os.environ.get("DHT11_GPIO", DEFAULT_GPIO)))
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    sensor = open_sensor(args.gpio)
    try:
        while True:
            last_error = None
            for _ in range(args.retries):
                try:
                    temperature, humidity = read_once(sensor)
                    print(f"{temperature:.1f} C  {humidity:.1f} %RH")
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - DHT11 checksum/timeouts are common
                    last_error = exc
                    time.sleep(args.interval)
            if last_error:
                print(f"failed after {args.retries} tries: {last_error}", file=sys.stderr)
                if not args.loop:
                    return 1
            if not args.loop:
                return 0
            time.sleep(args.interval)
    finally:
        sensor.exit()


if __name__ == "__main__":
    raise SystemExit(main())
