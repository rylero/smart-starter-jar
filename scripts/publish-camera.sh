#!/usr/bin/env bash
# Publish the CSI camera over the internet via a Cloudflare quick tunnel.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/smart-starter-jar"
TOKEN_FILE="$CONFIG_DIR/stream.token"
URL_FILE="$CONFIG_DIR/public-url.txt"
LOG_DIR="${TMPDIR:-/tmp}/smart-starter-jar"
STREAM_BIND="${STREAM_BIND:-127.0.0.1}"
STREAM_PORT="${STREAM_PORT:-8080}"
STREAM_WIDTH="${STREAM_WIDTH:-1280}"
STREAM_HEIGHT="${STREAM_HEIGHT:-720}"
STREAM_FPS="${STREAM_FPS:-8}"

mkdir -p "$CONFIG_DIR" "$LOG_DIR"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_cloudflared() {
  if need_cmd cloudflared; then
    return
  fi
  echo "Installing cloudflared..."
  local tmp
  tmp="$(mktemp)"
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" -o "$tmp"
  chmod +x "$tmp"
  sudo mv "$tmp" /usr/local/bin/cloudflared
}

ensure_token() {
  if [[ -n "${STREAM_TOKEN:-}" ]]; then
    printf '%s\n' "$STREAM_TOKEN" > "$TOKEN_FILE"
  elif [[ -f "$TOKEN_FILE" ]]; then
    STREAM_TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
  else
    STREAM_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
    printf '%s\n' "$STREAM_TOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
  fi
  export STREAM_TOKEN
}

require_camera() {
  if ! need_cmd rpicam-hello; then
    echo "rpicam-hello is missing. On Raspberry Pi OS: sudo apt install rpicam-apps-core" >&2
    exit 1
  fi
  local listing
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
}

cleanup() {
  local pid
  for pid in "${PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
PIDS=()
trap cleanup EXIT INT TERM

require_camera
install_cloudflared
ensure_token

SERVER_LOG="$LOG_DIR/camera-server.log"
TUNNEL_LOG="$LOG_DIR/cloudflared.log"
: > "$TUNNEL_LOG"

python3 "$ROOT/camera/server.py" \
  --bind "$STREAM_BIND" \
  --port "$STREAM_PORT" \
  --token "$STREAM_TOKEN" \
  --width "$STREAM_WIDTH" \
  --height "$STREAM_HEIGHT" \
  --fps "$STREAM_FPS" \
  >"$SERVER_LOG" 2>&1 &
PIDS+=("$!")

for _ in $(seq 1 25); do
  if curl -fsS "http://${STREAM_BIND}:${STREAM_PORT}/t/${STREAM_TOKEN}/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "${PIDS[0]}" 2>/dev/null; then
    echo "Camera server failed to start. Log: $SERVER_LOG" >&2
    cat "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 0.2
done

cloudflared tunnel --no-autoupdate --url "http://${STREAM_BIND}:${STREAM_PORT}" \
  >"$TUNNEL_LOG" 2>&1 &
PIDS+=("$!")

PUBLIC_URL=""
for _ in $(seq 1 40); do
  PUBLIC_URL="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare.com' "$TUNNEL_LOG" | head -n 1 || true)"
  if [[ -n "$PUBLIC_URL" ]]; then
    break
  fi
  if ! kill -0 "${PIDS[1]}" 2>/dev/null; then
    echo "cloudflared exited. Log: $TUNNEL_LOG" >&2
    cat "$TUNNEL_LOG" >&2 || true
    exit 1
  fi
  sleep 0.5
done

if [[ -z "$PUBLIC_URL" ]]; then
  echo "Timed out waiting for a Cloudflare URL. Log: $TUNNEL_LOG" >&2
  cat "$TUNNEL_LOG" >&2 || true
  exit 1
fi

VIEW_URL="${PUBLIC_URL}/t/${STREAM_TOKEN}/"
printf '%s\n' "$VIEW_URL" > "$URL_FILE"
chmod 600 "$URL_FILE"

cat <<EOF

CSI camera is live.

Local:  http://${STREAM_BIND}:${STREAM_PORT}/t/${STREAM_TOKEN}/
Public: ${VIEW_URL}

The public URL changes each time this script starts.
Token file: $TOKEN_FILE
Press Ctrl+C to stop.
EOF

wait
