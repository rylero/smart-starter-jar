#!/usr/bin/env bash
# Free GPIO 17 from the kernel DHT11 overlay and install a userspace reader.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="/boot/firmware/config.txt"
LINE="dtoverlay=dht11,gpiopin=17"

if grep -qF "$LINE" "$CONFIG"; then
  sudo sed -i "/^# DHT11 data on BCM GPIO 17$/d;/^${LINE}$/d" "$CONFIG"
  echo "Removed $LINE from $CONFIG"
fi

if sudo dtoverlay -l | grep -q dht11; then
  sudo dtoverlay -r dht11
  echo "Unloaded dht11 overlay"
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  python3 -m venv --system-site-packages "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install --upgrade adafruit-circuitpython-dht
echo "DHT11 userspace reader is ready"
