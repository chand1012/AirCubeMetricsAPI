import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

from aircube_metrics_api.main import open_serial, parse_sensor_line
from aircube_metrics_api.storage import AirCubeAggregate, AirCubeReading, AirCubeStore


DEFAULT_PORT = "/dev/cu.usbmodem1101"
DEFAULT_BAUD = 115200
DEFAULT_DATABASE_URL = "sqlite:///./aircube.sqlite3"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_CLEANUP_INTERVAL = timedelta(minutes=5)

logger = logging.getLogger(__name__)


class AirCubeState:
    def __init__(self, store=None, cleanup_interval=DEFAULT_CLEANUP_INTERVAL):
        self._lock = threading.Lock()
        self.store = store or AirCubeStore(
            os.environ.get("AIRCUBE_DATABASE_URL", DEFAULT_DATABASE_URL),
            retention_days=_get_retention_days(),
        )
        self.cleanup_interval = cleanup_interval
        self._last_cleanup = None
        self.registry = CollectorRegistry()
        self.temperature_c = Gauge(
            "aircube_temperature_celsius",
            "AirCube temperature in Celsius",
            registry=self.registry,
        )
        self.humidity = Gauge(
            "aircube_humidity_percent",
            "AirCube relative humidity percent",
            registry=self.registry,
        )
        self.eco2 = Gauge(
            "aircube_eco2_ppm",
            "AirCube equivalent CO2 in ppm",
            registry=self.registry,
        )
        self.etvoc = Gauge(
            "aircube_etvoc_ppb",
            "AirCube equivalent TVOC in ppb",
            registry=self.registry,
        )
        self.voc_level = Gauge(
            "aircube_voc_level",
            "AirCube VOC Level from 0 to 500",
            registry=self.registry,
        )
        self.uptime_ms = Gauge(
            "aircube_uptime_milliseconds",
            "AirCube uptime in milliseconds",
            registry=self.registry,
        )

    def update(self, reading):
        latest = self.store.add_reading(reading)
        with self._lock:
            self.temperature_c.set(latest.temp_c)
            self.humidity.set(latest.humidity)
            self.eco2.set(latest.eco2)
            self.etvoc.set(latest.etvoc)
            self.voc_level.set(latest.voc_level)
            self.uptime_ms.set(latest.timestamp_ms)
            self._cleanup_if_needed()
        return latest

    def latest(self):
        return self.store.latest()

    def query(self, start=None, end=None, limit=1000):
        return self.store.query_readings(start=start, end=end, limit=limit)

    def query_aggregates(self, start=None, end=None, aggregate="day"):
        return self.store.query_aggregates(start=start, end=end, aggregate=aggregate)

    def create_schema(self):
        self.store.create_schema()

    def cleanup(self):
        deleted = self.store.cleanup()
        self._last_cleanup = datetime.now(UTC)
        return deleted

    def _cleanup_if_needed(self):
        now = datetime.now(UTC)
        if self._last_cleanup is None or now - self._last_cleanup >= self.cleanup_interval:
            self.store.cleanup(now=now)
            self._last_cleanup = now


def serial_worker(state, stop_event, port, baud=DEFAULT_BAUD):
    try:
        logger.info("Starting AirCube serial reader on %s at %s baud", port, baud)
        with open_serial(port, baud) as ser:
            logger.info("AirCube serial port opened: %s", port)
            received_reading = False
            while not stop_event.is_set():
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                try:
                    reading = parse_sensor_line(line)
                except Exception:
                    logger.warning("Failed to parse AirCube serial line: %r", line, exc_info=True)
                    continue
                if reading is None:
                    logger.debug("Ignoring non-reading AirCube serial line: %r", line)
                    continue
                state.update(reading)
                if not received_reading:
                    logger.info("Received first AirCube reading from %s", port)
                    received_reading = True
    except Exception:
        logger.exception("AirCube serial reader stopped unexpectedly for port %s", port)


def create_app(state=None, start_serial=False, port=None, baud=DEFAULT_BAUD):
    state = state or AirCubeState()

    @asynccontextmanager
    async def lifespan(app):
        stop_event = threading.Event()
        thread = None
        state.create_schema()
        state.cleanup()

        if start_serial:
            serial_port = port or os.environ.get("AIRCUBE_PORT", DEFAULT_PORT)
            thread = threading.Thread(
                target=serial_worker,
                args=(state, stop_event, serial_port, baud),
                daemon=True,
            )
            thread.start()

        yield

        stop_event.set()
        if thread is not None:
            thread.join(timeout=2)

    app = FastAPI(lifespan=lifespan)

    @app.get("/latest", response_model=AirCubeReading)
    def latest():
        reading = state.latest()
        if reading is None:
            raise HTTPException(status_code=503, detail="No AirCube reading available yet")
        return reading

    @app.get("/query")
    def query(
        start: datetime | None = None,
        end: datetime | None = None,
        aggregate: Literal["hour", "day"] | None = None,
        limit: int = 1000,
    ) -> list[AirCubeReading] | list[AirCubeAggregate]:
        if aggregate is not None:
            return state.query_aggregates(start=start, end=end, aggregate=aggregate)
        return state.query(start=start, end=end, limit=limit)

    @app.get("/metrics")
    def metrics():
        return Response(
            generate_latest(state.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


def _get_retention_days():
    return int(os.environ.get("AIRCUBE_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))


app = create_app(start_serial=True)
