#!/usr/bin/env bash
# Flash each capture LED by itself so wiring can be checked.
set -euo pipefail

PINS=(${LIGHT_GPIOS:-23 24})

for pin in "${PINS[@]}"; do
  echo "GPIO $pin on"
  pinctrl set "$pin" op dh
  sleep 1
  pinctrl set "$pin" op dl
  echo "GPIO $pin off"
  sleep 0.4
done
