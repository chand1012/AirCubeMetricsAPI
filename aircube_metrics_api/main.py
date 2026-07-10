import json
import sys


def parse_sensor_line(line):
    if not line.startswith("{"):
        return None

    data = json.loads(line)
    return {
        "temp_c": data["ens210"]["temperature_c"],
        "humidity": data["ens210"]["humidity"],
        "eco2": data["ens16x"]["eco2"],
        "etvoc": data["ens16x"]["etvoc"],
        "voc_level": data["ens16x"]["aqi"],
        "timestamp_ms": data["timestamp"],
    }


def open_serial(port, baud=115200):
    import serial

    return serial.serial_for_url(port, baud, timeout=1)


def read_aircube(port, baud=115200):
    with open_serial(port, baud) as ser:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            reading = parse_sensor_line(line)
            if reading is not None:
                print(reading)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: uv run aircube-read <serial-port>", file=sys.stderr)
        return 2

    read_aircube(argv[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
