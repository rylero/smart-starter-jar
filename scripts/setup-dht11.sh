#!/usr/bin/env bash
# Load the DHT11 overlay on BCM GPIO 18 (physical pin 12).
set -euo pipefail

CONFIG="/boot/firmware/config.txt"
LINE="dtoverlay=dht11,gpiopin=18"

sudo sed -i '/^# DHT11 data on BCM GPIO 1[78]$/d;/^dtoverlay=dht11,gpiopin=1[78]$/d' "$CONFIG"
printf '\n# DHT11 data on BCM GPIO 18\n%s\n' "$LINE" | sudo tee -a "$CONFIG" >/dev/null
echo "Wrote $LINE to $CONFIG"

if sudo dtoverlay -l | grep -q dht11; then
  sudo dtoverlay -r dht11
fi
sudo dtoverlay dht11 gpiopin=18
echo "Loaded dht11 overlay on GPIO 18"
