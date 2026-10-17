#!/usr/bin/env python3
"""Serve a CSI camera MJPEG view from rpicam-vid."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

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

    def wait(self, previous: Optional[bytes] = None, timeout: float = 5.0) -> Optional[bytes]:
        with self._cond:
            if self._frame is not None and self._frame is not previous:
                return self._frame
            self._cond.wait(timeout)
            return self._frame


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


def start_camera(width: int, height: int, fps: int, extra_args: list[str]) -> subprocess.Popen:
    rpicam = shutil.which("rpicam-vid")
    if not rpicam:
        raise SystemExit("rpicam-vid not found. Install rpicam-apps-core.")

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


def build_handler(frames: LatestFrame, token: str, page_title: str):
    expected = f"/t/{token}"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _authorized_path(self) -> Optional[str]:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query_token = parse_qs(parsed.query).get("token", [None])[0]
            if path == expected or path.startswith(expected + "/"):
                return path[len(expected) :] or "/"
            if query_token == token and path in {"/", "/stream.mjpg", "/health"}:
                return path
            return None

        def _deny(self) -> None:
            body = b"unauthorized\n"
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = self._authorized_path()
            if path is None:
                self._deny()
                return
            if path in {"/", "/index.html"}:
                self._html()
                return
            if path in {"/stream.mjpg", "/stream"}:
                self._stream()
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

        def _html(self) -> None:
            src = f"{expected}/stream.mjpg"
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    html, body {{ margin: 0; height: 100%; background: #111; color: #eee; font-family: sans-serif; }}
    .wrap {{ min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; }}
    img {{ max-width: 100%; max-height: 92vh; background: #000; }}
    h1 {{ font-size: 1rem; font-weight: 600; margin: 0; letter-spacing: 0.02em; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{page_title}</h1>
    <img src="{src}" alt="Live CSI camera">
  </div>
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
                    frame = frames.wait(previous)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default=os.environ.get("STREAM_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STREAM_PORT", "8080")))
    parser.add_argument("--token", default=os.environ.get("STREAM_TOKEN"))
    parser.add_argument("--width", type=int, default=int(os.environ.get("STREAM_WIDTH", "1280")))
    parser.add_argument("--height", type=int, default=int(os.environ.get("STREAM_HEIGHT", "720")))
    parser.add_argument("--fps", type=int, default=int(os.environ.get("STREAM_FPS", "8")))
    parser.add_argument("--title", default=os.environ.get("STREAM_TITLE", "Smart Starter Jar"))
    args, extra = parser.parse_known_args()
    extra = extra or [part for part in os.environ.get("RPICAM_EXTRA_ARGS", "").split() if part]

    if not args.token:
        raise SystemExit("STREAM_TOKEN or --token is required")

    camera = start_camera(args.width, args.height, args.fps, extra)
    if camera.stdout is None:
        raise SystemExit("failed to open rpicam-vid stdout")

    frames = LatestFrame()

    def pump() -> None:
        for frame in iter_jpeg_frames(camera.stdout):
            frames.set(frame)
        camera.wait()

    reader = threading.Thread(target=pump, name="rpicam-mjpeg", daemon=True)
    reader.start()

    handler = build_handler(frames, args.token, args.title)
    server = ThreadingHTTPServer((args.bind, args.port), handler)

    def shutdown(*_sig) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"local viewer: http://{args.bind}:{args.port}/t/{args.token}/", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        camera.terminate()
        try:
            camera.wait(timeout=5)
        except subprocess.TimeoutExpired:
            camera.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
