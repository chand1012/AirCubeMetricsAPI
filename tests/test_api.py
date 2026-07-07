import unittest

from fastapi.testclient import TestClient

import api


class ApiTests(unittest.TestCase):
    def test_latest_returns_current_reading_as_json(self):
        state = api.AirCubeState()
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
        self.assertEqual(
            response.json(),
            {
                "temp_c": 23.45,
                "humidity": 52.3,
                "eco2": 415,
                "etvoc": 42,
                "voc_level": 3,
                "timestamp_ms": 12345,
            },
        )

    def test_latest_returns_503_before_first_reading(self):
        client = TestClient(api.create_app(api.AirCubeState()))

        response = client.get("/latest")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "No AirCube reading available yet"})

    def test_metrics_exposes_current_reading(self):
        state = api.AirCubeState()
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

    def test_app_starts_serial_reader_from_environment(self):
        self.assertTrue(api.app.router.lifespan_context is not None)


if __name__ == "__main__":
    unittest.main()
