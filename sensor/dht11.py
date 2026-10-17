#!/usr/bin/env python3
"""Read a DHT11 on BCM GPIO 18 (physical pin 12) via the kernel IIO driver."""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

DEFAULT_GPIO = 18


def find_iio_device() -> str:
    for path in glob.glob("/sys/bus/iio/devices/iio:device*"):
        try:
            name = open(os.path.join(path, "name"), encoding="ascii").read().strip()
        except OSError:
            continue
        if name.startswith("dht11"):
            return path
    raise RuntimeError(
        "DHT11 IIO device not found. Run ./scripts/setup-dht11.sh then retry."
    )


def read_once(device: str) -> tuple[float, float]:
    temperature = int(open(os.path.join(device, "in_temp_input"), encoding="ascii").read())
    humidity = int(open(os.path.join(device, "in_humidityrelative_input"), encoding="ascii").read())
    return temperature / 1000.0, humidity / 1000.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpio", type=int, default=int(os.environ.get("DHT11_GPIO", DEFAULT_GPIO)))
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    device = find_iio_device()
    while True:
        last_error = None
        for _ in range(args.retries):
            try:
                temperature, humidity = read_once(device)
                print(f"{temperature:.1f} C  {humidity:.1f} %RH")
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                time.sleep(args.interval)
        if last_error:
            print(f"failed after {args.retries} tries: {last_error}", file=sys.stderr)
            if not args.loop:
                return 1
        if not args.loop:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
