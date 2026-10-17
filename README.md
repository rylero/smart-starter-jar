# Smart Starter Jar

Raspberry Pi 4 project for a sourdough starter jar: CSI camera height/timelapse, plus a temperature and humidity sensor.

## Live camera

On the Pi, with the camera seated in the **CAM** CSI port:

```bash
git clone https://github.com/rylero/smart-starter-jar.git
cd smart-starter-jar
./scripts/publish-camera.sh
```

The script starts a local MJPEG viewer from `rpicam-vid` and publishes it with a Cloudflare quick tunnel. It prints a public `https://…trycloudflare.com` link. Anyone with that URL and token can see the camera.

The URL changes every run. The access token is stored in `~/.config/smart-starter-jar/stream.token`.

Optional environment variables: `STREAM_WIDTH`, `STREAM_HEIGHT`, `STREAM_FPS`, `STREAM_TOKEN`, `RPICAM_EXTRA_ARGS` (for `--vflip`, `--hflip`, or `--rotation`).

## Pi image

`pi/flash-sd.ps1` writes Raspberry Pi OS Lite 64-bit with SSH over Ethernet. Copy `pi/cloud-init/user-data.example` to `user-data` and fill in your password hash and SSH key before flashing.
