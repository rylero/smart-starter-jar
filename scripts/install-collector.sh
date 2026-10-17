#!/usr/bin/env bash
# Install the collector systemd unit. Does not start it unless --now is passed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="$ROOT/systemd/starter-jar.service"
UNIT_DST=/etc/systemd/system/starter-jar.service

sudo cp "$UNIT_SRC" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable starter-jar.service
if [[ "${1:-}" == "--now" ]]; then
  sudo systemctl start starter-jar.service
  echo "starter-jar.service enabled and started"
else
  echo "starter-jar.service enabled. Start later with: sudo systemctl start starter-jar"
fi
