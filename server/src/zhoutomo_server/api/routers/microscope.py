"""Microscope state, parameter, and command endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from zhoutomo_protocol import CommandRequest, CommandResponse, ComponentParamsRequest
from zhoutomo_server.api.dependencies import get_microscope_aggregate
from zhoutomo_server.services import MicroscopeService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Microscope"])


def get_microscope_service(aggregate=Depends(get_microscope_aggregate)) -> MicroscopeService:
    return MicroscopeService(aggregate)


@router.get("/snapshot")
async def get_snapshot(service: MicroscopeService = Depends(get_microscope_service)):
    try:
        return service.get_snapshot()
    except Exception as exc:
        logger.error("Failed to get snapshot: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/components")
async def list_components(service: MicroscopeService = Depends(get_microscope_service)):
    try:
        return {"components": service.list_components()}
    except Exception as exc:
        logger.error("Failed to list components: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/components/{component}/state")
async def get_component_state(
    component: str,
    service: MicroscopeService = Depends(get_microscope_service),
):
    try:
        return service.get_component_state(component)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Component {component} not found") from exc
    except Exception as exc:
        logger.error("Failed to get component %s state: %s", component, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/params")
async def get_params(service: MicroscopeService = Depends(get_microscope_service)):
    return service.get_parameter_schema()


@router.patch("/components/{component}/params")
async def set_component_params(
    component: str,
    request: ComponentParamsRequest,
    service: MicroscopeService = Depends(get_microscope_service),
):
    try:
        success = service.set_component_params(component, request.params)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update {component} parameters",
            )
        return {"message": f"Successfully updated {component} parameters"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Component {component} not found") from exc
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid parameter value: {exc}") from exc
    except Exception as exc:
        logger.error("Failed to set %s params: %s", component, exc)
        raise HTTPException(status_code=500, detail=f"Failed to set component params: {exc}") from exc


@router.post("/components/{component}/commands/{command}", tags=["Commands"])
async def execute_command(
    component: str,
    command: str,
    request: CommandRequest,
    service: MicroscopeService = Depends(get_microscope_service),
) -> CommandResponse:
    try:
        service.execute_command(component, command, request.parameters or {})
        return CommandResponse(
            success=True,
            message=f"Command {command} executed successfully",
            timestamp=datetime.now().isoformat(),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Component {component} not found") from exc
    except Exception as exc:
        logger.error("Failed to execute %s on %s: %s", command, component, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
