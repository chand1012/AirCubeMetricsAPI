AirCube Metrics API
===================

Standalone `uv` project for reading AirCube sensor JSON from a serial port and
exposing the latest reading through FastAPI and Prometheus metrics.

Run locally:

```sh
uv sync
uv run uvicorn aircube_metrics_api.api:app --host 0.0.0.0 --port 8000
```

By default the API reads `/dev/cu.usbmodem1101`. Override it with
`AIRCUBE_PORT`:

```sh
AIRCUBE_PORT=/dev/ttyACM0 uv run uvicorn aircube_metrics_api.api:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /latest` returns the most recent parsed sensor reading.
- `GET /metrics` returns Prometheus metrics.

Read directly from the device without the API:

```sh
uv run aircube-read /dev/ttyACM0
```

Run in Docker with a forwarded serial device:

```sh
docker build -t aircube-metrics-api .
docker run --rm \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  -e AIRCUBE_PORT=/dev/ttyACM0 \
  -p 8000:8000 \
  aircube-metrics-api
```

Or with Compose:

```sh
AIRCUBE_PORT=/dev/ttyACM0 docker compose up --build
```

On macOS, Docker Desktop cannot directly pass every host serial device into a
Linux container. If the direct `--device` mapping is unavailable for your
adapter, expose the serial device to Docker through a Linux VM or a serial TCP
bridge and set `AIRCUBE_PORT` to the device path available inside the container.
