#!/usr/bin/env bash
# Turn the capture light on GPIO 24 for one second.
set -euo pipefail

GPIO="${LIGHT_GPIO:-24}"

pinctrl set "$GPIO" op dh
sleep 1
pinctrl set "$GPIO" op dl
