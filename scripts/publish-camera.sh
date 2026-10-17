#!/usr/bin/env bash
# Serve the CSI camera as a local MJPEG page.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STREAM_BIND="${STREAM_BIND:-0.0.0.0}"
STREAM_PORT="${STREAM_PORT:-8080}"
STREAM_WIDTH="${STREAM_WIDTH:-1280}"
STREAM_HEIGHT="${STREAM_HEIGHT:-720}"
STREAM_FPS="${STREAM_FPS:-8}"

if ! command -v rpicam-hello >/dev/null 2>&1; then
  echo "rpicam-hello is missing. On Raspberry Pi OS: sudo apt install rpicam-apps-core" >&2
  exit 1
fi

listing="$(rpicam-hello --list-cameras 2>&1 || true)"
if printf '%s\n' "$listing" | grep -qi 'No cameras available'; then
  cat >&2 <<'EOF'
No CSI camera was detected.

Seat the ribbon in the CAM port (not DISP), contacts toward the HDMI
ports, then reboot:

  sudo reboot

After reboot: rpicam-hello --list-cameras
EOF
  exit 1
fi
echo "$listing"

ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Opening local viewer on http://${ip:-localhost}:${STREAM_PORT}/"
echo "Press Ctrl+C to stop."

exec python3 "$ROOT/camera/server.py" \
  --bind "$STREAM_BIND" \
  --port "$STREAM_PORT" \
  --width "$STREAM_WIDTH" \
  --height "$STREAM_HEIGHT" \
  --fps "$STREAM_FPS"
