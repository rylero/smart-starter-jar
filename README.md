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

Data line is **BCM GPIO 18** (physical pin 12). Power the module from 3.3V or 5V, depending on the breakout, and share a GND with the Pi.

```bash
./scripts/setup-dht11.sh
./scripts/read-dht11.sh
./scripts/read-dht11.sh --loop
```

## Collector

`collector.py` writes DHT11 samples to the same InfluxDB 1.x instance as the [WeatherStation logger](https://github.com/rylero/WeatherStation/blob/main/logger.py) and saves a CSI still about every 15 minutes under `data/timelapse/YYYY-MM-DD/`. GPIO 24 turns on for each frame.

```bash
sudo apt install -y python3-influxdb
cp config.example.env .env
./scripts/install-collector.sh        # enable on boot, do not start
# ./scripts/install-collector.sh --now
```

Defaults match the WeatherStation client: `homeassistant.local:8086`, user `home_assistant`, database `starter_jar`. Override them in `.env`. Sensor period is 60s; frame period is 900s.

## Pi image

`pi/flash-sd.ps1` writes Raspberry Pi OS Lite 64-bit with SSH over Ethernet. Copy `pi/cloud-init/user-data.example` to `user-data` and fill in your password hash and SSH key before flashing.
