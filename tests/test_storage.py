import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from aircube_metrics_api.storage import AirCubeStore


def reading(temp_c, recorded_at):
    return {
        "temp_c": temp_c,
        "humidity": 50.0 + temp_c,
        "eco2": 400 + temp_c,
        "etvoc": 20 + temp_c,
        "voc_level": temp_c,
        "timestamp_ms": int(temp_c * 1000),
        "recorded_at": recorded_at,
    }


class AirCubeStoreTests(unittest.TestCase):
    def make_store(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3")
        self.addCleanup(tmp.close)
        store = AirCubeStore(f"sqlite:///{tmp.name}")
        store.create_schema()
        self.addCleanup(store.close)
        return store

    def test_latest_returns_newest_reading_by_recorded_at(self):
        store = self.make_store()
        older = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
        newer = datetime(2026, 7, 8, 10, 5, tzinfo=UTC)

        store.add_reading(reading(20.0, older))
        latest = store.add_reading(reading(21.0, newer))

        self.assertEqual(store.latest(), latest)
        self.assertEqual(store.latest().temp_c, 21.0)

    def test_query_readings_returns_rows_inside_time_window(self):
        store = self.make_store()
        start = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
        store.add_reading(reading(19.0, start - timedelta(minutes=1)))
        inside = store.add_reading(reading(20.0, start + timedelta(minutes=5)))
        store.add_reading(reading(21.0, start + timedelta(hours=2)))

        rows = store.query_readings(start=start, end=start + timedelta(hours=1))

        self.assertEqual(rows, [inside])

    def test_query_daily_averages_returns_aggregated_buckets(self):
        store = self.make_store()
        day_one = datetime(2026, 7, 7, 10, 0, tzinfo=UTC)
        day_two = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
        store.add_reading(reading(20.0, day_one))
        store.add_reading(reading(22.0, day_one + timedelta(hours=1)))
        store.add_reading(reading(30.0, day_two))

        buckets = store.query_aggregates(start=day_one, end=day_two + timedelta(days=1), aggregate="day")

        self.assertEqual(len(buckets), 2)
        self.assertEqual(buckets[0].bucket, "2026-07-07")
        self.assertEqual(buckets[0].temp_c, 21.0)
        self.assertEqual(buckets[0].sample_count, 2)
        self.assertEqual(buckets[1].bucket, "2026-07-08")
        self.assertEqual(buckets[1].temp_c, 30.0)
        self.assertEqual(buckets[1].sample_count, 1)

    def test_cleanup_deletes_readings_older_than_retention_window(self):
        store = self.make_store()
        now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
        store.add_reading(reading(20.0, now - timedelta(days=8)))
        kept = store.add_reading(reading(21.0, now - timedelta(days=6, hours=23)))

        deleted = store.cleanup(now=now)

        self.assertEqual(deleted, 1)
        self.assertEqual(store.query_readings(), [kept])


if __name__ == "__main__":
    unittest.main()
