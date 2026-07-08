# AirCube Metrics API

Turn an AirCube sensor on a serial port into a small, container-friendly
metrics service.

AirCube Metrics API reads newline-delimited JSON from an AirCube device,
stores the last seven days of readings in SQLite, and exposes the data as
JSON, queryable time windows, aggregate buckets, and Prometheus metrics. It is
intentionally boring in the best way: one process, one serial reader, one
FastAPI app, and a Docker image that can run anywhere you can forward the
device.

## What You Get

- FastAPI endpoint for the latest AirCube reading
- SQLite storage for the last seven days of sensor history
- Query endpoint for raw rows, hourly averages, and daily averages
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
curl "http://localhost:8000/query?aggregate=day"
curl http://localhost:8000/metrics
```

## Docker

Build locally:

```sh
docker build -t aircube-metrics-api .
```

Run with a forwarded serial device and a persistent SQLite database:

```sh
mkdir -p data

docker run --rm \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  -e AIRCUBE_PORT=/dev/ttyACM0 \
  -e AIRCUBE_DATABASE_URL=sqlite:////data/aircube.sqlite3 \
  -e AIRCUBE_RETENTION_DAYS=7 \
  -v "$PWD/data:/data" \
  -p 8000:8000 \
  aircube-metrics-api
```

The `--device` flag forwards the AirCube serial port into the container. The
`-v "$PWD/data:/data"` mount keeps `aircube.sqlite3` on the host so the last
seven days of readings survive container restarts.

Run with Compose:

```sh
mkdir -p data
AIRCUBE_PORT=/dev/ttyACM0 docker compose up --build
```

Compose uses the same runtime shape: `${AIRCUBE_PORT}` is forwarded as a device,
`./data` is mounted at `/data`, `AIRCUBE_DATABASE_URL` defaults to
`sqlite:////data/aircube.sqlite3`, and `AIRCUBE_RETENTION_DAYS` defaults to `7`.

Use the published GHCR image:

```sh
mkdir -p data

docker run --rm \
  --device=/dev/ttyACM0:/dev/ttyACM0 \
  -e AIRCUBE_PORT=/dev/ttyACM0 \
  -e AIRCUBE_DATABASE_URL=sqlite:////data/aircube.sqlite3 \
  -e AIRCUBE_RETENTION_DAYS=7 \
  -v "$PWD/data:/data" \
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

Returns the newest reading stored in SQLite.

Example response:

```json
{
  "id": 1,
  "recorded_at": "2026-07-08T14:21:00.000000",
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

### `GET /query`

Returns SQLModel-shaped readings from SQLite. Without an aggregate, the
endpoint returns raw `AirCubeReading` rows ordered by `recorded_at`.

Get the last hour of data:

```sh
curl "http://localhost:8000/query?start=2026-07-08T13:00:00Z&end=2026-07-08T14:00:00Z"
```

Limit raw results:

```sh
curl "http://localhost:8000/query?limit=100"
```

Get hourly averages:

```sh
curl "http://localhost:8000/query?aggregate=hour&start=2026-07-08T00:00:00Z"
```

Get daily averages:

```sh
curl "http://localhost:8000/query?aggregate=day"
```

Aggregate responses include averaged sensor fields and a sample count:

```json
[
  {
    "bucket": "2026-07-08",
    "temp_c": 23.1,
    "humidity": 52.8,
    "eco2": 417.5,
    "etvoc": 43.2,
    "voc_level": 3.0,
    "sample_count": 1440
  }
]
```

Supported query parameters:

| Parameter | Description |
| --- | --- |
| `start` | Inclusive ISO-8601 lower bound for `recorded_at` |
| `end` | Exclusive ISO-8601 upper bound for `recorded_at` |
| `aggregate` | Optional bucket mode: `hour` or `day` |
| `limit` | Raw row limit when `aggregate` is omitted; default `1000` |

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
| `AIRCUBE_DATABASE_URL` | `sqlite:///./aircube.sqlite3` | SQLModel database URL for persisted readings |
| `AIRCUBE_RETENTION_DAYS` | `7` | Number of days to retain SQLite readings before cleanup |
| `AIRCUBE_API_PORT` | `8000` | Host port used by `docker-compose.yml` |

The serial baud rate is `115200`. Readings older than `AIRCUBE_RETENTION_DAYS`
are deleted on startup and periodically after inserts.

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
  storage.py   SQLModel table and SQLite query helpers
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
