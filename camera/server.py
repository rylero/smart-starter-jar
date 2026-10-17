#!/usr/bin/env python3
"""Serve a CSI camera MJPEG view from rpicam-vid."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

import light

JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"


class LatestFrame:
    def __init__(self) -> None:
        self._frame: Optional[bytes] = None
        self._cond = threading.Condition()

    def set(self, frame: bytes) -> None:
        with self._cond:
            self._frame = frame
            self._cond.notify_all()

    def get(self) -> Optional[bytes]:
        with self._cond:
            return self._frame

    def wait(self, previous: Optional[bytes] = None, timeout: float = 5.0) -> Optional[bytes]:
        with self._cond:
            if self._frame is not None and self._frame is not previous:
                return self._frame
            self._cond.wait(timeout)
            return self._frame


class AppState:
    def __init__(self, frames: LatestFrame, title: str = "Smart Starter Jar") -> None:
        self.frames = frames
        self.title = title
        self.lock = threading.Lock()
        self.temp_c: Optional[float] = None
        self.humidity: Optional[float] = None

    def set_reading(self, temp_c: float, humidity: float) -> None:
        with self.lock:
            self.temp_c = temp_c
            self.humidity = humidity

    def status(self) -> dict:
        with self.lock:
            return {
                "light": light.is_on(),
                "temp_c": self.temp_c,
                "humidity": self.humidity,
            }


def iter_jpeg_frames(stream) -> None:
    buf = bytearray()
    while True:
        chunk = stream.read(4096)
        if not chunk:
            return
        buf.extend(chunk)
        while True:
            start = buf.find(JPEG_START)
            if start == -1:
                if len(buf) > 1_000_000:
                    del buf[:-2]
                break
            if start > 0:
                del buf[:start]
            end = buf.find(JPEG_END, 2)
            if end == -1:
                break
            yield bytes(buf[: end + 2])
            del buf[: end + 2]


def start_camera(width: int, height: int, fps: float, extra_args: list[str]) -> subprocess.Popen:
    rpicam = shutil.which("rpicam-vid")
    if not rpicam:
        raise RuntimeError("rpicam-vid not found. Install rpicam-apps-core.")

    cmd = [
        rpicam,
        "--timeout",
        "0",
        "--nopreview",
        "--codec",
        "mjpeg",
        "--inline",
        "--width",
        str(width),
        "--height",
        str(height),
        "--framerate",
        str(fps),
        "--output",
        "-",
        *extra_args,
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )


def start_frame_pump(camera: subprocess.Popen, frames: LatestFrame) -> threading.Thread:
    if camera.stdout is None:
        raise RuntimeError("failed to open rpicam-vid stdout")

    def pump() -> None:
        for frame in iter_jpeg_frames(camera.stdout):
            frames.set(frame)
        camera.wait()

    reader = threading.Thread(target=pump, name="rpicam-mjpeg", daemon=True)
    reader.start()
    return reader


def build_handler(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path in {"/", "/index.html"}:
                self._html()
                return
            if path in {"/stream.mjpg", "/stream"}:
                self._stream()
                return
            if path in {"/status", "/light"}:
                self._json(state.status())
                return
            if path == "/health":
                body = b"ok\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/light":
                light.toggle()
                self._json(state.status())
                return
            if path == "/light/on":
                self._json({"light": light.set_light(True)})
                return
            if path == "/light/off":
                self._json({"light": light.set_light(False)})
                return
            self.send_error(404)

        def _html(self) -> None:
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{state.title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    html, body {{ margin: 0; height: 100%; background: #111; color: #eee; font-family: sans-serif; }}
    .wrap {{ min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 16px; box-sizing: border-box; }}
    img {{ max-width: 100%; max-height: 78vh; background: #000; }}
    h1 {{ font-size: 1rem; font-weight: 600; margin: 0; }}
    .row {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; justify-content: center; }}
    button {{ font: inherit; padding: 8px 14px; border: 0; border-radius: 8px; background: #2a2a2a; color: #eee; cursor: pointer; }}
    button.on {{ background: #c9a227; color: #111; }}
    #stats {{ opacity: 0.8; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{state.title}</h1>
    <img src="/stream.mjpg" alt="Live CSI camera">
    <div class="row">
      <button id="light" type="button">Light</button>
      <span id="stats"></span>
    </div>
  </div>
  <script>
    const button = document.getElementById("light");
    const stats = document.getElementById("stats");
    async function refresh() {{
      const response = await fetch("/status");
      const data = await response.json();
      button.textContent = data.light ? "Light on" : "Light off";
      button.classList.toggle("on", !!data.light);
      stats.textContent = data.temp_c == null ? "" : data.temp_c.toFixed(1) + " C  " + data.humidity.toFixed(1) + " %RH";
    }}
    button.addEventListener("click", async () => {{
      await fetch("/light", {{ method: "POST" }});
      refresh();
    }});
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            previous = None
            try:
                while True:
                    frame = state.frames.wait(previous)
                    if frame is None or frame is previous:
                        continue
                    previous = frame
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(frame)).encode("ascii")
                        + b"\r\n\r\n"
                        + frame
                        + b"\r\n"
                    )
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

    return Handler


def start_http(state: AppState, bind: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((bind, port), build_handler(state))
    thread = threading.Thread(target=server.serve_forever, name="http", daemon=True)
    thread.start()
    print(f"local viewer: http://{bind}:{port}/", flush=True)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default=os.environ.get("STREAM_BIND", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STREAM_PORT", "8080")))
    parser.add_argument("--width", type=int, default=int(os.environ.get("STREAM_WIDTH", "1280")))
    parser.add_argument("--height", type=int, default=int(os.environ.get("STREAM_HEIGHT", "720")))
    parser.add_argument("--fps", type=int, default=int(os.environ.get("STREAM_FPS", "8")))
    parser.add_argument("--title", default=os.environ.get("STREAM_TITLE", "Smart Starter Jar"))
    args, extra = parser.parse_known_args()
    extra = extra or [part for part in os.environ.get("RPICAM_EXTRA_ARGS", "").split() if part]

    light.set_light(False)
    camera = start_camera(args.width, args.height, args.fps, extra)
    frames = LatestFrame()
    start_frame_pump(camera, frames)
    state = AppState(frames, args.title)
    server = start_http(state, args.bind, args.port)

    stop = threading.Event()

    def shutdown(*_sig) -> None:
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        stop.wait()
    finally:
        server.shutdown()
        server.server_close()
        camera.terminate()
        try:
            camera.wait(timeout=5)
        except subprocess.TimeoutExpired:
            camera.kill()
        light.set_light(False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
