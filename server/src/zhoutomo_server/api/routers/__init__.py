"""FastAPI routers grouped by transport responsibility."""

from . import acquisition, diagnostics, microscope, system, websocket

__all__ = ["acquisition", "diagnostics", "microscope", "system", "websocket"]
