"""Black-box Client -> HTTP -> Null Server integration tests.

The CI job starts zhoutomo-server in a separate process before running this file
inside the client uv environment.
"""

import os

import pytest

from zhoutomo_client.api import AgentClient


BASE_URL = os.getenv("ZHOUTOMO_TEST_SERVER_URL", "http://127.0.0.1:9000")


@pytest.mark.asyncio
async def test_agent_client_round_trip_against_null_server():
    client = AgentClient(BASE_URL, timeout=5.0, max_retries=1)
    await client.connect()
    try:
        assert await client.is_connected()

        health = await client.get_health()
        assert health["status"] == "healthy"
        assert health["microscope_connected"] is True

        components = await client.get_components()
        assert "stage" in components["components"]
        assert "acquisition" in components["components"]

        snapshot = await client.get_snapshot()
        assert "stage" in snapshot
        assert "acquisition" in snapshot

        update = await client.set_component_params(
            "acquisition",
            {"acq_image_size": 64, "frames": 1},
        )
        assert "Successfully updated" in update["message"]

        acquisition_state = await client.get_component_state("acquisition")
        assert acquisition_state["frames"] == 1
        assert acquisition_state["acq_image_size"] == 64

        acquisition = await client.start_acquisition()
        assert acquisition["success"] is True
        assert acquisition["count"] == 1
        assert len(acquisition["frames"]) == 1

        status = await client.get_acquisition_status()
        assert status["active"] is False

        stopped = await client.stop_acquisition()
        assert stopped["success"] is True
    finally:
        await client.disconnect()
