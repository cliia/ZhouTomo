"""Runtime state owned by the ZhouTomo server process."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from zhoutomo_protocol import API_VERSION, FrameData
from zhoutomo_server.wiring import MicroscopeWiring

logger = logging.getLogger(__name__)


class ServerState:
    """Mutable process state shared by API transports and services."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.version = API_VERSION
        self.microscope_wiring: Optional[MicroscopeWiring] = None
        self.acquisition_task: Optional[asyncio.Task] = None
        self.websocket_connections: list[WebSocket] = []

    def get_uptime(self) -> float:
        return time.time() - self.start_time

    def is_microscope_connected(self) -> bool:
        if self.microscope_wiring is None:
            return False
        try:
            return self.microscope_wiring.is_connected()
        except Exception as exc:
            logger.error("Error checking microscope connection: %s", exc)
            return False

    async def start_acquisition(self) -> None:
        """Start the background frame-publishing loop if it is not running."""
        if self.acquisition_task is None or self.acquisition_task.done():
            self.acquisition_task = asyncio.create_task(self._acquisition_loop())
            logger.info("Acquisition task started")

    async def stop_acquisition(self) -> None:
        """Stop the background frame-publishing loop."""
        if self.acquisition_task and not self.acquisition_task.done():
            self.acquisition_task.cancel()
            try:
                await self.acquisition_task
            except asyncio.CancelledError:
                pass
            logger.info("Acquisition task stopped")

    async def _acquisition_loop(self) -> None:
        acquisition_initialized = False
        while True:
            try:
                if not self.is_microscope_connected():
                    acquisition_initialized = False
                    await asyncio.sleep(5.0)
                    continue

                wiring = self.microscope_wiring
                mode = getattr(wiring, "mode", "null") if wiring else "null"
                aggregate = wiring.get_aggregate() if wiring else None

                if not acquisition_initialized and aggregate is not None:
                    try:
                        if aggregate.has_component("acquisition"):
                            aggregate.execute_command("acquisition", "start")
                        acquisition_initialized = True
                    except Exception as exc:
                        logger.warning("Failed to start hardware acquisition: %s", exc)

                image_bytes = None
                try:
                    microscope = wiring.get_microscope() if wiring else None
                    camera = getattr(microscope, "camera", None) if microscope else None
                    if camera is None and microscope is not None:
                        components = getattr(microscope, "_components", {})
                        camera = components.get("camera")
                    acquire_fn = getattr(camera, "acquire_image", None)
                    if callable(acquire_fn):
                        loop = asyncio.get_running_loop()
                        image_bytes = await loop.run_in_executor(None, acquire_fn)
                except Exception as exc:
                    logger.warning("Failed to acquire image from hardware: %s", exc)

                if image_bytes:
                    frame = FrameData(
                        frame_id=str(uuid.uuid4()),
                        timestamp=time.time(),
                        component="camera",
                        data=image_bytes,
                        metadata={"width": 1024, "height": 1024, "source": mode},
                    )
                    await self.broadcast_frame(frame)

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                try:
                    wiring = self.microscope_wiring
                    aggregate = wiring.get_aggregate() if wiring else None
                    if aggregate and aggregate.has_component("acquisition"):
                        aggregate.execute_command("acquisition", "stop")
                except Exception:
                    pass
                break
            except Exception as exc:
                logger.error("Error in acquisition loop: %s", exc)
                await asyncio.sleep(5.0)

    async def broadcast_frame(self, frame: FrameData) -> None:
        """Broadcast frame metadata to all currently connected WebSockets."""
        if not self.websocket_connections:
            return

        self.websocket_connections = [
            connection
            for connection in self.websocket_connections
            if connection.client_state != WebSocketState.DISCONNECTED
        ]

        payload = {
            "type": "frame",
            "data": {
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp,
                "component": frame.component,
                "metadata": frame.metadata,
            },
        }
        for websocket in list(self.websocket_connections):
            try:
                await websocket.send_json(payload)
            except Exception as exc:
                logger.warning("Failed to send frame to websocket: %s", exc)
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)


server_state = ServerState()
