# Smart Starter Jar

Raspberry Pi 4 project for a sourdough starter jar: CSI camera height/timelapse, plus a temperature and humidity sensor.

## Live camera

On the Pi, with the camera seated in the **CAM** CSI port:

```bash
git clone https://github.com/rylero/smart-starter-jar.git
cd smart-starter-jar
./scripts/publish-camera.sh
```

Then open `http://<pi-ip>:8080/` on the same network. The page is an MJPEG view from the CSI camera via `rpicam-vid`.

Optional environment variables: `STREAM_WIDTH`, `STREAM_HEIGHT`, `STREAM_FPS`, `STREAM_BIND`, `STREAM_PORT`, `RPICAM_EXTRA_ARGS` (for `--vflip`, `--hflip`, or `--rotation`).

## DHT11 temperature and humidity

Data line is **BCM GPIO 17** (physical pin 11). Power the module from 3.3V or 5V, depending on the breakout, and share a GND with the Pi.

```bash
./scripts/setup-dht11.sh
./scripts/read-dht11.sh
./scripts/read-dht11.sh --loop
```

## Pi image

`pi/flash-sd.ps1` writes Raspberry Pi OS Lite 64-bit with SSH over Ethernet. Copy `pi/cloud-init/user-data.example` to `user-data` and fill in your password hash and SSH key before flashing.
