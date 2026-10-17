#!/usr/bin/env bash
# Turn the capture lights on GPIO 23 and 24 for one second.
set -euo pipefail

PINS=(${LIGHT_GPIOS:-23 24})

for pin in "${PINS[@]}"; do
  pinctrl set "$pin" op dh
done
sleep 1
for pin in "${PINS[@]}"; do
  pinctrl set "$pin" op dl
done
