import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

from aircube_metrics_api.main import parse_sensor_line


DEFAULT_PORT = "/dev/cu.usbmodem1101"
DEFAULT_BAUD = 115200


class AirCubeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = None
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
        latest = dict(reading)
        with self._lock:
            self._latest = latest
            self.temperature_c.set(latest["temp_c"])
            self.humidity.set(latest["humidity"])
            self.eco2.set(latest["eco2"])
            self.etvoc.set(latest["etvoc"])
            self.voc_level.set(latest["voc_level"])
            self.uptime_ms.set(latest["timestamp_ms"])

    def latest(self):
        with self._lock:
            if self._latest is None:
                return None
            return dict(self._latest)


def serial_worker(state, stop_event, port, baud=DEFAULT_BAUD):
    import serial

    with serial.Serial(port, baud, timeout=1) as ser:
        while not stop_event.is_set():
            line = ser.readline().decode(errors="ignore").strip()
            reading = parse_sensor_line(line)
            if reading is not None:
                state.update(reading)


def create_app(state=None, start_serial=False, port=None, baud=DEFAULT_BAUD):
    state = state or AirCubeState()

    @asynccontextmanager
    async def lifespan(app):
        stop_event = threading.Event()
        thread = None

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

    @app.get("/latest")
    def latest():
        reading = state.latest()
        if reading is None:
            raise HTTPException(status_code=503, detail="No AirCube reading available yet")
        return reading

    @app.get("/metrics")
    def metrics():
        return Response(
            generate_latest(state.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app(start_serial=True)
