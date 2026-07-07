import json
import unittest
from unittest.mock import patch

import main


class MainTests(unittest.TestCase):
    def test_parse_aircube_json_line_returns_minimal_sensor_fields(self):
        line = json.dumps(
            {
                "ens210": {
                    "temperature_c": 23.45,
                    "humidity": 52.3,
                },
                "ens16x": {
                    "eco2": 415,
                    "etvoc": 42,
                    "aqi": 3,
                },
                "timestamp": 12345,
            }
        )

        self.assertEqual(
            main.parse_sensor_line(line),
            {
                "temp_c": 23.45,
                "humidity": 52.3,
                "eco2": 415,
                "etvoc": 42,
                "voc_level": 3,
                "timestamp_ms": 12345,
            },
        )

    def test_parse_sensor_line_ignores_non_json_lines(self):
        self.assertIsNone(main.parse_sensor_line("ESP_LOGI booting"))

    def test_main_prints_usage_when_serial_port_is_missing(self):
        with patch("sys.stderr") as stderr:
            exit_code = main.main([])

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "Usage: uv run aircube-read <serial-port>",
            "".join(call.args[0] for call in stderr.write.call_args_list),
        )


if __name__ == "__main__":
    unittest.main()
