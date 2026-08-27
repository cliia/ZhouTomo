"""Command-line entry point for the ZhouTomo microscope server."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from zhoutomo_server.api import create_app, set_microscope_wiring
from zhoutomo_server.state import ServerState
from zhoutomo_server.wiring import (
    MicroscopeWiring,
    create_microscope_wiring,
    get_available_modes,
    validate_mode,
)

logger = logging.getLogger(__name__)


class AgentConfig:
    """Runtime configuration. Priority: CLI > environment > code defaults."""

    def __init__(self) -> None:
        self.mode: str = "local"
        self.server_url: Optional[str] = None
        self.host: str = "0.0.0.0"
        self.port: int = 9000
        self.reload: bool = False
        self.log_level: str = "INFO"
        self.config_file: Optional[str] = None
        self.info: bool = False

    def load_from_env(self) -> None:
        self.mode = os.getenv("AGENT_MODE", self.mode)
        self.server_url = os.getenv("AGENT_SERVER_URL", self.server_url)
        self.host = os.getenv("AGENT_HOST", self.host)
        self.port = int(os.getenv("AGENT_PORT", str(self.port)))
        self.reload = os.getenv("AGENT_RELOAD", str(self.reload)).lower() == "true"
        self.log_level = os.getenv("AGENT_LOG_LEVEL", self.log_level)

    def validate(self) -> bool:
        if not validate_mode(self.mode):
            logger.error("Invalid mode: %s", self.mode)
            return False
        if self.mode == "remote" and not self.server_url:
            logger.error("Remote mode requires server_url")
            return False
        if not 1 <= self.port <= 65535:
            logger.error("Invalid port: %s", self.port)
            return False
        return True

    def __str__(self) -> str:
        return (
            f"AgentConfig(mode={self.mode}, server_url={self.server_url}, "
            f"host={self.host}, port={self.port})"
        )


class AgentManager:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.wiring: Optional[MicroscopeWiring] = None
        self.server_state: Optional[ServerState] = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self) -> bool:
        try:
            logger.info("Initializing agent...")
            self.wiring = create_microscope_wiring(
                mode=self.config.mode,
                server_url=self.config.server_url,
            )
            if not self._connect_microscope():
                logger.error("Failed to connect to microscope")
                return False
            self.server_state = ServerState()
            logger.info("Agent initialized successfully")
            return True
        except Exception as exc:
            logger.error("Failed to initialize agent: %s", exc)
            return False

    def _connect_microscope(self) -> bool:
        try:
            if self.wiring is None or not self.wiring.connect():
                return False
            if not self.wiring.is_connected():
                logger.error("Microscope not connected")
                return False
            info = self.wiring.get_info()
            logger.info("Connected to microscope: %s", info.get("name", "Unknown"))
            return True
        except Exception as exc:
            logger.error("Error connecting to microscope: %s", exc)
            return False

    async def shutdown(self) -> None:
        logger.info("Shutting down agent...")
        self.shutdown_event.set()
        if self.wiring:
            self.wiring.disconnect()
        logger.info("Agent shutdown completed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ZhouTomo microscope server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["local", "remote", "null"],
        default=None,
        help="Microscope mode (default: AGENT_MODE or local)",
    )
    parser.add_argument("--server_url", default=None)
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host (default: AGENT_HOST or 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: AGENT_PORT or 9000)",
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ZhouTomo Server v1.0.0",
    )
    parser.add_argument("--info", action="store_true")
    return parser


def parse_arguments(argv: list[str] | None = None) -> AgentConfig:
    args = build_parser().parse_args(argv)
    config = AgentConfig()
    config.load_from_env()

    if args.mode is not None:
        config.mode = args.mode
    if args.server_url is not None:
        config.server_url = args.server_url
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.reload is not None:
        config.reload = args.reload
    if args.log_level is not None:
        config.log_level = args.log_level
    if args.config is not None:
        config.config_file = args.config
    config.info = args.info
    return config


def setup_logging(config: AgentConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("agent.log", encoding="utf-8"),
        ],
        force=True,
    )
    if config.mode == "null":
        logging.getLogger("zhoutomo_server.wiring").setLevel(logging.DEBUG)


def show_system_info() -> None:
    print("ZhouTomo microscope server")
    print("=" * 40)
    print("\nAvailable modes:")
    for mode, available in get_available_modes().items():
        print(f"  {'✓' if available else '✗'} {mode}")
    print(f"\nPython: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print("Environment:")
    for name in ("AGENT_MODE", "AGENT_SERVER_URL", "AGENT_HOST", "AGENT_PORT"):
        print(f"  {name}: {os.getenv(name, 'not set')}")


def setup_signal_handlers(agent_manager: AgentManager) -> None:
    def signal_handler(signum, frame) -> None:
        logger.info("Received signal %s, initiating shutdown...", signum)
        asyncio.create_task(agent_manager.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal_handler)


async def run(config: AgentConfig) -> None:
    if config.info:
        show_system_info()
        return

    setup_logging(config)
    if not config.validate():
        raise SystemExit(1)

    logger.info("Starting server with config: %s", config)
    agent_manager = AgentManager(config)
    try:
        if not await agent_manager.initialize():
            raise SystemExit(1)

        setup_signal_handlers(agent_manager)
        set_microscope_wiring(agent_manager.wiring)
        app = create_app()

        import uvicorn

        uvicorn_config = uvicorn.Config(
            app=app,
            host=config.host,
            port=config.port,
            reload=config.reload,
            log_level=config.log_level.lower(),
            access_log=True,
            http="h11",
        )
        server = uvicorn.Server(uvicorn_config)
        logger.info("Starting server on %s:%s", config.host, config.port)
        logger.info("Mode: %s", config.mode)
        if config.server_url:
            logger.info("Remote server: %s", config.server_url)
        await server.serve()
    finally:
        await agent_manager.shutdown()


def main() -> None:
    config = parse_arguments()
    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")


if __name__ == "__main__":
    main()
