import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import api
from aircube_metrics_api.storage import AirCubeStore


class ApiTests(unittest.TestCase):
    def make_store(self):
        store = AirCubeStore("sqlite:///:memory:")
        store.create_schema()
        self.addCleanup(store.close)
        return store

    def test_latest_returns_current_reading_as_json(self):
        store = self.make_store()
        state = api.AirCubeState(store=store)
        state.update(
            {
                "temp_c": 23.45,
                "humidity": 52.3,
                "eco2": 415,
                "etvoc": 42,
                "voc_level": 3,
                "timestamp_ms": 12345,
            }
        )

        client = TestClient(api.create_app(state))
        response = client.get("/latest")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["temp_c"], 23.45)
        self.assertEqual(body["humidity"], 52.3)
        self.assertEqual(body["eco2"], 415)
        self.assertEqual(body["etvoc"], 42)
        self.assertEqual(body["voc_level"], 3)
        self.assertEqual(body["timestamp_ms"], 12345)
        self.assertIn("recorded_at", body)

    def test_latest_returns_503_before_first_reading(self):
        client = TestClient(api.create_app(api.AirCubeState(store=self.make_store())))

        response = client.get("/latest")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "No AirCube reading available yet"})

    def test_metrics_exposes_current_reading(self):
        state = api.AirCubeState(store=self.make_store())
        state.update(
            {
                "temp_c": 23.45,
                "humidity": 52.3,
                "eco2": 415,
                "etvoc": 42,
                "voc_level": 3,
                "timestamp_ms": 12345,
            }
        )

        client = TestClient(api.create_app(state))
        response = client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("aircube_temperature_celsius 23.45", response.text)
        self.assertIn("aircube_humidity_percent 52.3", response.text)
        self.assertIn("aircube_eco2_ppm 415.0", response.text)
        self.assertIn("aircube_etvoc_ppb 42.0", response.text)
        self.assertIn("aircube_voc_level 3.0", response.text)
        self.assertIn("aircube_uptime_milliseconds 12345.0", response.text)

    def test_query_returns_readings_inside_time_window(self):
        store = self.make_store()
        base = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
        store.add_reading(
            {
                "temp_c": 20.0,
                "humidity": 50.0,
                "eco2": 400,
                "etvoc": 20,
                "voc_level": 1,
                "timestamp_ms": 1000,
                "recorded_at": base - timedelta(minutes=1),
            }
        )
        store.add_reading(
            {
                "temp_c": 21.0,
                "humidity": 51.0,
                "eco2": 401,
                "etvoc": 21,
                "voc_level": 2,
                "timestamp_ms": 2000,
                "recorded_at": base + timedelta(minutes=5),
            }
        )

        client = TestClient(api.create_app(api.AirCubeState(store=store)))
        response = client.get(
            "/query",
            params={
                "start": base.isoformat().replace("+00:00", "Z"),
                "end": (base + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["temp_c"], 21.0)

    def test_query_returns_daily_aggregate_buckets(self):
        store = self.make_store()
        day = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
        for temp_c in (20.0, 22.0):
            store.add_reading(
                {
                    "temp_c": temp_c,
                    "humidity": 50.0,
                    "eco2": 400,
                    "etvoc": 20,
                    "voc_level": 2,
                    "timestamp_ms": 1000,
                    "recorded_at": day,
                }
            )

        client = TestClient(api.create_app(api.AirCubeState(store=store)))
        response = client.get("/query", params={"aggregate": "day"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "bucket": "2026-07-08",
                    "temp_c": 21.0,
                    "humidity": 50.0,
                    "eco2": 400.0,
                    "etvoc": 20.0,
                    "voc_level": 2.0,
                    "sample_count": 2,
                }
            ],
        )

    def test_aircube_state_uses_default_retention_days(self):
        state = api.AirCubeState()
        self.addCleanup(state.store.close)

        self.assertEqual(state.store.retention_days, 7)

    def test_aircube_state_uses_retention_days_from_environment(self):
        with patch.dict("os.environ", {"AIRCUBE_RETENTION_DAYS": "3"}):
            state = api.AirCubeState()
            self.addCleanup(state.store.close)

        self.assertEqual(state.store.retention_days, 3)

    def test_app_starts_serial_reader_from_environment(self):
        self.assertTrue(api.app.router.lifespan_context is not None)

    def test_serial_worker_logs_serial_open_failures(self):
        stop_event = Mock()
        stop_event.is_set.return_value = False

        with patch("aircube_metrics_api.api.open_serial", side_effect=RuntimeError("device missing")):
            with self.assertLogs("aircube_metrics_api.api", level="ERROR") as logs:
                api.serial_worker(Mock(), stop_event, "/dev/ttyACM0")

        self.assertIn(
            "AirCube serial reader stopped unexpectedly for port /dev/ttyACM0",
            "\n".join(logs.output),
        )

    def test_serial_worker_logs_parse_failures_and_keeps_reading(self):
        state = Mock()
        stop_event = Mock()
        stop_event.is_set.side_effect = [False, False, True]
        serial_port = Mock()
        serial_port.readline.side_effect = [
            b'{"ens210": {}}\n',
            (
                b'{"ens210":{"temperature_c":23.45,"humidity":52.3},'
                b'"ens16x":{"eco2":415,"etvoc":42,"aqi":3},"timestamp":12345}\n'
            ),
        ]
        serial_context = Mock()
        serial_context.__enter__ = Mock(return_value=serial_port)
        serial_context.__exit__ = Mock(return_value=False)

        with patch("aircube_metrics_api.api.open_serial", return_value=serial_context):
            with self.assertLogs("aircube_metrics_api.api", level="WARNING") as logs:
                api.serial_worker(state, stop_event, "/dev/ttyACM0")

        self.assertIn("Failed to parse AirCube serial line", "\n".join(logs.output))
        state.update.assert_called_once_with(
            {
                "temp_c": 23.45,
                "humidity": 52.3,
                "eco2": 415,
                "etvoc": 42,
                "voc_level": 3,
                "timestamp_ms": 12345,
            }
        )


if __name__ == "__main__":
    unittest.main()
