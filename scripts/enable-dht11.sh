#!/usr/bin/env bash
# Persist and load the DHT11 overlay on BCM GPIO 17.
set -euo pipefail

CONFIG="/boot/firmware/config.txt"
LINE="dtoverlay=dht11,gpiopin=17"

if ! grep -qxF "$LINE" "$CONFIG"; then
  printf '\n# DHT11 data on BCM GPIO 17\n%s\n' "$LINE" | sudo tee -a "$CONFIG" >/dev/null
  echo "Wrote $LINE to $CONFIG"
else
  echo "Overlay already in $CONFIG"
fi

if ! sudo dtoverlay -l | grep -q dht11; then
  sudo dtoverlay dht11 gpiopin=17
  echo "Loaded dht11 overlay"
else
  echo "dht11 overlay already loaded"
fi
