# AirCube Metrics API

Turn an AirCube sensor on a serial port into a small, container-friendly
metrics service.

AirCube Metrics API reads newline-delimited JSON from an AirCube device,
keeps the latest valid reading in memory, and exposes it as both JSON and
Prometheus metrics. It is intentionally boring in the best way: one process,
one serial reader, one FastAPI app, and a Docker image that can run anywhere
you can forward the device.

## What You Get

- FastAPI endpoint for the latest AirCube reading
- Prometheus `/metrics` endpoint for dashboards and alerting
- Direct serial reader CLI for quick debugging
- `uv` based Python project with a locked dependency graph
- Docker and Compose support with serial device forwarding
- GitHub Actions workflow that publishes `latest` to GHCR on pushes to `main`

## Quick Start

Install dependencies:

```sh
uv sync
```

Run the API against the default serial device:

```sh
uv run uvicorn aircube_metrics_api.api:app --host 0.0.0.0 --port 8000
```

Override the serial port:

```sh
AIRCUBE_PORT=/dev/ttyACM0 \
  uv run uvicorn aircube_metrics_api.api:app --host 0.0.0.0 --port 8000
```

Check it:

```sh
curl http://localhost:8000/latest
curl http://localhost:8000/metrics
```

## Docker

Build locally:

```sh
docker build -t aircube-metrics-api .
```

Run with a forwarded serial device:

```sh
docker run --rm \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  -e AIRCUBE_PORT=/dev/ttyACM0 \
  -p 8000:8000 \
  aircube-metrics-api
```

Run with Compose:

```sh
AIRCUBE_PORT=/dev/ttyACM0 docker compose up --build
```

Use the published GHCR image:

```sh
docker run --rm \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  -e AIRCUBE_PORT=/dev/ttyACM0 \
  -p 8000:8000 \
  ghcr.io/chand1012/aircubemetricsapi:latest
```

### Serial Ports In Docker

Linux hosts can usually pass a serial device directly with `--device`.

Common device names:

- Linux USB CDC devices: `/dev/ttyACM0`
- Linux USB serial adapters: `/dev/ttyUSB0`
- macOS local device path: `/dev/cu.usbmodem1101`

Docker Desktop on macOS does not expose every host serial device directly to
Linux containers. If direct device forwarding is unavailable, run the container
from a Linux host or VM that can see the device, or expose the serial device
through a bridge that creates a usable device path inside the container.

## API

### `GET /latest`

Returns the most recent valid AirCube reading.

Example response:

```json
{
  "temp_c": 23.45,
  "humidity": 52.3,
  "eco2": 415,
  "etvoc": 42,
  "voc_level": 3,
  "timestamp_ms": 12345
}
```

If the service has not received a valid reading yet, it returns:

```json
{
  "detail": "No AirCube reading available yet"
}
```

with HTTP status `503`.

### `GET /metrics`

Returns Prometheus text format metrics:

```text
aircube_temperature_celsius 23.45
aircube_humidity_percent 52.3
aircube_eco2_ppm 415.0
aircube_etvoc_ppb 42.0
aircube_voc_level 3.0
aircube_uptime_milliseconds 12345.0
```

## Serial Data Format

The parser expects each valid reading to be a JSON object on a single line.
Non-JSON log lines are ignored.

Expected input shape:

```json
{
  "ens210": {
    "temperature_c": 23.45,
    "humidity": 52.3
  },
  "ens16x": {
    "eco2": 415,
    "etvoc": 42,
    "aqi": 3
  },
  "timestamp": 12345
}
```

## CLI

Read and print parsed AirCube readings directly from a serial device:

```sh
uv run aircube-read /dev/ttyACM0
```

This is useful when you want to confirm the device is streaming data before
running the API or container.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `AIRCUBE_PORT` | `/dev/cu.usbmodem1101` | Serial device path used by the API reader |
| `AIRCUBE_API_PORT` | `8000` | Host port used by `docker-compose.yml` |

The serial baud rate is `115200`.

## Development

Run tests:

```sh
uv run python -m unittest discover -s tests
```

Run the app locally without Docker:

```sh
AIRCUBE_PORT=/dev/ttyACM0 \
  uv run uvicorn aircube_metrics_api.api:app --reload
```

Project layout:

```text
aircube_metrics_api/
  api.py       FastAPI app, Prometheus state, serial worker
  main.py      serial parser and direct reader CLI
tests/         parser and API behavior tests
Dockerfile     production container image
docker-compose.yml
```

## Publishing

The GitHub Actions workflow at `.github/workflows/publish-ghcr.yml` builds and
pushes this image on every push to `main`:

```text
ghcr.io/chand1012/aircubemetricsapi:latest
```

## License

MIT. See `LICENSE`.
