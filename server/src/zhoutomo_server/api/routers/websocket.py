"""WebSocket transport for frame metadata and control messages."""

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from zhoutomo_server.state import server_state

logger = logging.getLogger(__name__)
router = APIRouter()


async def handle_websocket_control(websocket: WebSocket, message: dict[str, Any]) -> None:
    command = message.get("command")
    try:
        if command == "set_frame_interval":
            interval = message.get("interval", 1.0)
            response = {
                "type": "control_response",
                "command": command,
                "success": True,
                "message": f"Frame interval set to {interval}s (simulated)",
            }
        else:
            response = {
                "type": "control_response",
                "command": command,
                "success": False,
                "message": f"Unknown command: {command}",
            }
        await websocket.send_text(json.dumps(response))
    except Exception as exc:
        logger.error("Failed to handle WebSocket control: %s", exc)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "control_response",
                    "command": command or "unknown",
                    "success": False,
                    "message": f"Error: {exc}",
                }
            )
        )


@router.websocket("/ws/frames")
async def websocket_frames(websocket: WebSocket) -> None:
    await websocket.accept()
    server_state.websocket_connections.append(websocket)

    try:
        while True:
            await websocket.send_text(json.dumps({"type": "heartbeat", "timestamp": time.time()}))
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from WebSocket: %s", data)
                continue

            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
            elif message.get("type") == "control":
                await handle_websocket_control(websocket, message)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
    finally:
        if websocket in server_state.websocket_connections:
            server_state.websocket_connections.remove(websocket)
