"""System and health endpoints."""

from datetime import datetime

from fastapi import APIRouter

from zhoutomo_protocol import HealthResponse
from zhoutomo_server.state import server_state

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version=server_state.version,
        microscope_connected=server_state.is_microscope_connected(),
        uptime=server_state.get_uptime(),
    )


@router.get("/version")
async def get_version() -> dict[str, object]:
    return {"version": server_state.version, "timestamp": datetime.now().isoformat()}


@router.get("/info")
async def get_system_info() -> dict[str, object]:
    return {
        "name": "ZhouTomo API Server",
        "version": server_state.version,
        "uptime": server_state.get_uptime(),
        "microscope_connected": server_state.is_microscope_connected(),
        "timestamp": datetime.now().isoformat(),
    }
