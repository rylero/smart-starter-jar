#!/usr/bin/env bash
# Turn the capture lights on for one second.
set -euo pipefail

PINS=(${LIGHT_GPIOS:-24 25})

for pin in "${PINS[@]}"; do
  pinctrl set "$pin" op dh
done
sleep 1
for pin in "${PINS[@]}"; do
  pinctrl set "$pin" op dl
done
