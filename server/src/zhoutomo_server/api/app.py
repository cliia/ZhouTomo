"""FastAPI application factory for the ZhouTomo microscope server."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zhoutomo_protocol import API_VERSION
from zhoutomo_server.api.dependencies import (
    get_microscope_aggregate,
    get_microscope_wiring,
    set_microscope_wiring,
)
from zhoutomo_server.api.routers import acquisition, diagnostics, microscope, system, websocket
from zhoutomo_server.state import server_state

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ZhouTomo API Server...")
    yield
    logger.info("Shutting down ZhouTomo API Server...")
    if server_state.microscope_wiring:
        server_state.microscope_wiring.disconnect()
    await server_state.stop_acquisition()


def register_routes(app: FastAPI) -> None:
    app.include_router(system.router)
    app.include_router(microscope.router)
    app.include_router(acquisition.router)
    app.include_router(diagnostics.router)
    app.include_router(websocket.router)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ZhouTomo API Server",
        description="显微镜控制系统的对外API接口",
        version=API_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app)
    return app


app = create_app()

__all__ = [
    "app",
    "create_app",
    "get_microscope_aggregate",
    "get_microscope_wiring",
    "lifespan",
    "register_routes",
    "set_microscope_wiring",
]
