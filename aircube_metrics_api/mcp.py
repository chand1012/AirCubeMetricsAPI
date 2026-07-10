from datetime import datetime
from typing import Literal

from fastmcp import FastMCP

from aircube_metrics_api.storage import AirCubeAggregate, AirCubeReading


def create_mcp_server(state) -> FastMCP:
    """Create an MCP server backed by the same state as the HTTP API."""
    mcp = FastMCP(
        name="AirCube Metrics",
        instructions=(
            "Use latest for the current AirCube sensor values. Use query for "
            "historical readings or hourly/daily averages. Times are ISO-8601."
        ),
    )

    @mcp.tool(name="latest")
    def latest() -> AirCubeReading:
        """Return the newest AirCube sensor reading."""
        reading = state.latest()
        if reading is None:
            raise ValueError("No AirCube reading is available yet")
        return reading

    @mcp.tool(name="query")
    def query(
        start: datetime | None = None,
        end: datetime | None = None,
        aggregate: Literal["hour", "day"] | None = None,
        limit: int = 1000,
    ) -> list[AirCubeReading | AirCubeAggregate]:
        """Query readings in a time window, optionally averaged by hour or day.

        `start` is inclusive and `end` is exclusive. `limit` applies only to
        raw readings; aggregate queries return every bucket in the time window.
        """
        if aggregate is not None:
            return state.query_aggregates(start=start, end=end, aggregate=aggregate)
        return state.query(start=start, end=end, limit=limit)

    return mcp
