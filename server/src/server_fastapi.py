"""Compatibility shim for the pre-package FastAPI module.

New code should import from :mod:`zhoutomo_server.api` and
:mod:`zhoutomo_server.state`.  This module remains temporarily so the legacy
``run_agent.py`` entry path continues to work during the staged migration.
"""

import argparse
import logging

import uvicorn

from zhoutomo_protocol import (
    CommandRequest,
    CommandResponse,
    ComponentParamsRequest,
    ErrorResponse,
    FrameData,
    HealthResponse,
)
from zhoutomo_server.api.app import (
    app,
    create_app,
    get_microscope_aggregate,
    get_microscope_wiring,
    lifespan,
    register_routes,
    set_microscope_wiring,
)
from zhoutomo_server.state import ServerState, server_state


def main() -> None:
    parser = argparse.ArgumentParser(description="ZhouTomo API Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
    )
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    uvicorn.run(
        "zhoutomo_server.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


__all__ = [
    "CommandRequest",
    "CommandResponse",
    "ComponentParamsRequest",
    "ErrorResponse",
    "FrameData",
    "HealthResponse",
    "ServerState",
    "app",
    "create_app",
    "get_microscope_aggregate",
    "get_microscope_wiring",
    "lifespan",
    "register_routes",
    "server_state",
    "set_microscope_wiring",
]


if __name__ == "__main__":
    main()
