"""Acquisition orchestration independent of the HTTP transport."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from zhoutomo_server.state import ServerState
from zhoutomo_server.wiring import MicroscopeWiring

logger = logging.getLogger(__name__)


class AcquisitionService:
    def __init__(self, state: ServerState) -> None:
        self.state = state

    async def acquire_once(self, wiring: MicroscopeWiring) -> dict[str, Any]:
        if not wiring.is_connected():
            raise RuntimeError("Microscope not connected")

        microscope = wiring.get_microscope()
        if microscope is None:
            raise RuntimeError("Microscope not available")

        loop = asyncio.get_running_loop()
        raw_frames = await loop.run_in_executor(None, microscope.start_acquisition)
        frames = self._normalize_to_frame_list(raw_frames)

        frames_b64: list[str] = []
        frame_shapes: list[list[int] | None] = []
        frame_dtypes: list[str | None] = []
        frame_byteorders: list[str | None] = []

        for frame in frames:
            shape, dtype_name, byteorder = self._frame_metadata(frame)
            try:
                raw = self._frame_to_bytes(frame)
            except Exception:
                raw = b"placeholder"
                shape = dtype_name = byteorder = None

            frames_b64.append(base64.b64encode(raw).decode("ascii"))
            frame_shapes.append(shape)
            frame_dtypes.append(dtype_name)
            frame_byteorders.append(byteorder)

        if frames_b64:
            logger.info(
                "[acq] first frame meta: shape=%s, dtype=%s, byteorder=%s",
                frame_shapes[0],
                frame_dtypes[0],
                frame_byteorders[0],
            )

        return {
            "success": True,
            "frames": frames_b64,
            "count": len(frames_b64),
            "frame_shapes": frame_shapes,
            "frame_dtypes": frame_dtypes,
            "frame_byteorders": frame_byteorders,
        }

    async def stop(self) -> dict[str, Any]:
        await self.state.stop_acquisition()
        return {"success": True, "message": "Acquisition stopped"}

    def is_active(self) -> bool:
        task = self.state.acquisition_task
        return task is not None and not task.done()

    @staticmethod
    def _normalize_to_frame_list(obj: Any) -> list[Any]:
        if obj is None:
            return []
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return [bytes(obj)]
        if hasattr(obj, "tobytes") and callable(obj.tobytes):
            return [obj]
        if isinstance(obj, (list, tuple)):
            return list(obj)
        return [obj]

    @staticmethod
    def _frame_to_bytes(obj: Any) -> bytes:
        if hasattr(obj, "Array"):
            obj = obj.Array
        if hasattr(obj, "tobytes") and callable(obj.tobytes):
            return obj.tobytes()
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return bytes(obj)
        return str(obj).encode("utf-8")

    @staticmethod
    def _frame_metadata(frame: Any) -> tuple[list[int] | None, str | None, str | None]:
        array = getattr(frame, "Array", None)
        height = width = None

        if hasattr(frame, "Height") and hasattr(frame, "Width"):
            try:
                height = int(frame.Height)
                width = int(frame.Width)
            except Exception:
                height = width = None
        elif hasattr(array, "shape") and len(array.shape) >= 2:
            height, width = int(array.shape[0]), int(array.shape[1])

        dtype_name = None
        byteorder = None
        if hasattr(array, "dtype"):
            dtype_name = getattr(array.dtype, "name", None)
            byteorder = getattr(array.dtype, "byteorder", None)

        shape = [height, width] if height is not None and width is not None else None
        return shape, dtype_name, byteorder
