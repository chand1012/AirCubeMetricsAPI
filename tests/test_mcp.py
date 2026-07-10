import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from fastmcp import Client

from aircube_metrics_api.api import AirCubeState, create_app
from aircube_metrics_api.mcp import create_mcp_server
from aircube_metrics_api.storage import AirCubeStore


class McpTests(unittest.IsolatedAsyncioTestCase):
    def make_state(self):
        store = AirCubeStore("sqlite:///:memory:")
        store.create_schema()
        self.addCleanup(store.close)
        return AirCubeState(store=store)

    async def test_server_exposes_latest_and_query_tools(self):
        state = self.make_state()
        mcp = create_mcp_server(state)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        self.assertEqual({tool.name for tool in tools}, {"latest", "query"})

    async def test_latest_returns_the_newest_reading(self):
        state = self.make_state()
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

        async with Client(create_mcp_server(state)) as client:
            result = await client.call_tool("latest", {})

        self.assertEqual(result.data.temp_c, 23.45)
        self.assertEqual(result.data.eco2, 415)

    async def test_query_supports_time_windows_and_aggregates(self):
        state = self.make_state()
        base = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
        for offset, temp_c in ((0, 20.0), (1, 22.0)):
            state.store.add_reading(
                {
                    "temp_c": temp_c,
                    "humidity": 50.0,
                    "eco2": 400,
                    "etvoc": 20,
                    "voc_level": 2,
                    "timestamp_ms": 1000 + offset,
                    "recorded_at": base + timedelta(minutes=offset),
                }
            )

        async with Client(create_mcp_server(state)) as client:
            result = await client.call_tool(
                "query",
                {
                    "start": base.isoformat(),
                    "end": (base + timedelta(hours=1)).isoformat(),
                    "aggregate": "hour",
                },
            )

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].temp_c, 21.0)
        self.assertEqual(result.data[0].sample_count, 2)

    def test_fastapi_app_mounts_mcp_endpoint(self):
        app = create_app(self.make_state())

        self.assertIn("/mcp", {route.path for route in app.routes})
        self.assertEqual(app.state.mcp.name, "AirCube Metrics")

        with TestClient(app) as client:
            self.assertEqual(client.get("/latest").status_code, 503)


if __name__ == "__main__":
    unittest.main()
