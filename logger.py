"""InfluxDB 1.x writer, same client style as the WeatherStation logger."""

from __future__ import annotations

import os
import sys
from time import gmtime, strftime

from influxdb import InfluxDBClient

INFLUX_HOST = os.environ.get("INFLUX_HOST", "homeassistant.local")
INFLUX_PORT = int(os.environ.get("INFLUX_PORT", "8086"))
INFLUX_USER = os.environ.get("INFLUX_USER", "home_assistant")
INFLUX_PASSWORD = os.environ.get("INFLUX_PASSWORD", "home_assistant")
INFLUX_DATABASE = os.environ.get("INFLUX_DATABASE", "starter_jar")
INFLUX_LOCATION = os.environ.get("INFLUX_LOCATION", "kitchen")

client = InfluxDBClient(
    INFLUX_HOST,
    INFLUX_PORT,
    INFLUX_USER,
    INFLUX_PASSWORD,
    INFLUX_DATABASE,
)

try:
    client.create_database(INFLUX_DATABASE)
except Exception as exc:  # noqa: BLE001 - first-run helper, ignore if it already exists
    print(f"influx create_database: {exc}", file=sys.stderr)


def log(temp_c: float, humidity: float, frame: str | None = None) -> None:
    body = [
        {
            "measurement": "starter_jar",
            "tags": {
                "location": INFLUX_LOCATION,
            },
            "time": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
            "fields": {
                "temp_c": float(temp_c),
                "humidity": float(humidity),
            },
        }
    ]
    if frame:
        body[0]["fields"]["frame"] = frame

    try:
        client.write_points(body)
    except Exception as exc:  # noqa: BLE001 - keep collecting if Influx is down
        print(f"influx write failed: {exc}", file=sys.stderr)
