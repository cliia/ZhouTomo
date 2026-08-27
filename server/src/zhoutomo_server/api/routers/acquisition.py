"""Acquisition HTTP endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from zhoutomo_server.api.dependencies import get_microscope_wiring
from zhoutomo_server.services import AcquisitionService
from zhoutomo_server.state import server_state
from zhoutomo_server.wiring import MicroscopeWiring

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/acquisition", tags=["Acquisition"])


def get_acquisition_service() -> AcquisitionService:
    return AcquisitionService(server_state)


@router.post("/start")
async def start_acquisition(
    wiring: MicroscopeWiring = Depends(get_microscope_wiring),
    service: AcquisitionService = Depends(get_acquisition_service),
):
    try:
        return await service.acquire_once(wiring)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to start acquisition: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
async def stop_acquisition(service: AcquisitionService = Depends(get_acquisition_service)):
    try:
        payload = await service.stop()
        payload["timestamp"] = datetime.now().isoformat()
        return payload
    except Exception as exc:
        logger.error("Failed to stop acquisition: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
async def get_acquisition_status(service: AcquisitionService = Depends(get_acquisition_service)):
    return {"active": service.is_active(), "timestamp": datetime.now().isoformat()}
