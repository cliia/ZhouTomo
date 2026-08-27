"""FastAPI dependency providers for microscope resources."""

import logging

from fastapi import Depends, HTTPException, status

from zhoutomo_server.state import server_state
from zhoutomo_server.wiring import MicroscopeWiring

logger = logging.getLogger(__name__)


def set_microscope_wiring(wiring: MicroscopeWiring) -> None:
    """Install the process-wide microscope wiring created by the composition root."""
    if wiring is None:
        raise ValueError("wiring must not be None")
    server_state.microscope_wiring = wiring
    logger.info("Microscope wiring set successfully, mode: %s", wiring.mode)


def get_microscope_wiring() -> MicroscopeWiring:
    wiring = server_state.microscope_wiring
    if wiring is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microscope not initialized",
        )
    return wiring


def get_microscope_aggregate(wiring: MicroscopeWiring = Depends(get_microscope_wiring)):
    if not wiring.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microscope not connected",
        )

    aggregate = wiring.get_aggregate()
    if aggregate is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microscope aggregate not available",
        )
    return aggregate
