#!/usr/bin/env python3
"""Read a DHT11 on BCM GPIO 17 via the kernel IIO driver, with lgpio fallback."""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time


DEFAULT_GPIO = 17


def find_iio_device() -> str | None:
    for path in glob.glob("/sys/bus/iio/devices/iio:device*"):
        name_path = os.path.join(path, "name")
        try:
            name = open(name_path, encoding="ascii").read().strip()
        except OSError:
            continue
        if name.startswith("dht11"):
            return path
    return None


def read_iio(device: str) -> tuple[float, float]:
    temp_raw = open(os.path.join(device, "in_temp_input"), encoding="ascii").read().strip()
    hum_raw = open(os.path.join(device, "in_humidityrelative_input"), encoding="ascii").read().strip()
    # IIO reports millidegree C and millipercent RH.
    return int(temp_raw) / 1000.0, int(hum_raw) / 1000.0


def read_lgpio(gpio: int) -> tuple[float, float]:
    import lgpio

    handle = lgpio.gpiochip_open(0)
    try:
        lgpio.gpio_claim_output(handle, gpio)
        lgpio.gpio_write(handle, gpio, 0)
        time.sleep(0.018)
        lgpio.gpio_free(handle, gpio)
        lgpio.gpio_claim_input(handle, gpio)

        deadline = time.monotonic() + 0.01
        while lgpio.gpio_read(handle, gpio) == 1:
            if time.monotonic() > deadline:
                raise TimeoutError("DHT11 did not pull the data line low")
        while lgpio.gpio_read(handle, gpio) == 0:
            if time.monotonic() > deadline:
                raise TimeoutError("DHT11 start-low timed out")
        while lgpio.gpio_read(handle, gpio) == 1:
            if time.monotonic() > deadline:
                raise TimeoutError("DHT11 start-high timed out")

        bits = []
        for _ in range(40):
            while lgpio.gpio_read(handle, gpio) == 0:
                if time.monotonic() > deadline + 0.01:
                    raise TimeoutError("DHT11 bit-low timed out")
            start = time.monotonic()
            while lgpio.gpio_read(handle, gpio) == 1:
                if time.monotonic() > deadline + 0.01:
                    raise TimeoutError("DHT11 bit-high timed out")
            bits.append(1 if (time.monotonic() - start) > 0.00004 else 0)

        bytes_ = [0, 0, 0, 0, 0]
        for i, bit in enumerate(bits):
            bytes_[i // 8] = (bytes_[i // 8] << 1) | bit
        humidity, humidity_dec, temp, temp_dec, checksum = bytes_
        if ((humidity + humidity_dec + temp + temp_dec) & 0xFF) != checksum:
            raise ValueError(f"DHT11 checksum failed: {bytes_}")
        return float(temp), float(humidity)
    finally:
        lgpio.gpiochip_close(handle)


def read_once(gpio: int, prefer: str) -> tuple[float, float, str]:
    iio = find_iio_device()
    errors = []
    if prefer != "lgpio" and iio:
        try:
            temp, humidity = read_iio(iio)
            return temp, humidity, "iio"
        except OSError as exc:
            errors.append(f"iio: {exc}")
    if prefer != "iio":
        try:
            temp, humidity = read_lgpio(gpio)
            return temp, humidity, "lgpio"
        except Exception as exc:  # noqa: BLE001 - surface the sensor failure
            errors.append(f"lgpio: {exc}")
    raise RuntimeError("; ".join(errors) or "no DHT11 reader available")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpio", type=int, default=int(os.environ.get("DHT11_GPIO", DEFAULT_GPIO)))
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between retries")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--prefer", choices=("auto", "iio", "lgpio"), default="auto")
    args = parser.parse_args()

    while True:
        last_error = None
        for attempt in range(1, args.retries + 1):
            try:
                temp, humidity, source = read_once(args.gpio, args.prefer)
                print(f"{temp:.1f} C  {humidity:.1f} %RH  ({source})")
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
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
