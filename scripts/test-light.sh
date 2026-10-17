#!/usr/bin/env bash
# Turn the capture lights on GPIO 23 and 24 for one second.
set -euo pipefail

PINS="${LIGHT_GPIOS:-23 24}"

# shellcheck disable=SC2086
pinctrl set $PINS op dh
sleep 1
# shellcheck disable=SC2086
pinctrl set $PINS op dl
