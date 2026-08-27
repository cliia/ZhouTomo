"""HTTP/WebSocket contract tests backed by the Null microscope."""

from fastapi.testclient import TestClient

from zhoutomo_server.api import create_app, set_microscope_wiring
from zhoutomo_server.state import server_state
from zhoutomo_server.wiring import create_null_wiring


def _make_client() -> TestClient:
    wiring = create_null_wiring()
    assert wiring.connect()
    set_microscope_wiring(wiring)
    return TestClient(create_app())


def test_null_server_system_and_snapshot_routes():
    with _make_client() as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"
        assert health.json()["microscope_connected"] is True

        components = client.get("/components")
        assert components.status_code == 200
        assert "stage" in components.json()["components"]
        assert "acquisition" in components.json()["components"]

        snapshot = client.get("/snapshot")
        assert snapshot.status_code == 200
        payload = snapshot.json()
        assert "stage" in payload
        assert "acquisition" in payload


def test_null_server_component_update_command_and_acquisition():
    with _make_client() as client:
        update = client.patch(
            "/components/acquisition/params",
            json={"params": {"acq_image_size": 64, "frames": 2}},
        )
        assert update.status_code == 200

        state = client.get("/components/acquisition/state")
        assert state.status_code == 200
        assert state.json()["frames"] == 2
        assert state.json()["acq_image_size"] == 64

        command = client.post(
            "/components/camera/commands/capture",
            json={"parameters": {}},
        )
        assert command.status_code == 200
        assert command.json()["success"] is True

        acquisition = client.post("/acquisition/start")
        assert acquisition.status_code == 200
        result = acquisition.json()
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["frames"]) == 2

        stopped = client.post("/acquisition/stop")
        assert stopped.status_code == 200
        assert stopped.json()["success"] is True


def test_null_server_rejects_unknown_component():
    with _make_client() as client:
        response = client.get("/components/not-a-component/state")
        assert response.status_code == 404


def test_null_server_websocket_ping_pong():
    with _make_client() as client:
        with client.websocket_connect("/ws/frames") as websocket:
            heartbeat = websocket.receive_json()
            assert heartbeat["type"] == "heartbeat"

            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
            assert pong["type"] == "pong"


def teardown_module():
    # Keep the singleton clean for other test modules in the same process.
    server_state.microscope_wiring = None
