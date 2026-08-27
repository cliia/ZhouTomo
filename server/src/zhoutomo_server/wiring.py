"""Composition root for microscope implementations.

This module selects local temscript, remote, or Null implementations and
assembles the server-side aggregate.  Hardware behavior remains implemented in
``zhoutomo_server.drivers.temscript``.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from zhoutomo_protocol import MicroscopeState
from zhoutomo_server.domain import MicroscopeAggregate, MicroscopeInterface
from zhoutomo_server.drivers.temscript import (
    NullMicroscope,
    create_temscript_microscope,
    validate_temscript_connection,
)

logger = logging.getLogger(__name__)


class MicroscopeFactoryError(Exception):
    """Raised when a microscope implementation cannot be created."""


class MicroscopeConnectionError(Exception):
    """Raised when a microscope connection cannot be established."""


class MicroscopeFactory(ABC):
    @abstractmethod
    def create_microscope(self) -> MicroscopeInterface:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_info(self) -> dict[str, Any]:
        raise NotImplementedError


class LocalTemscriptFactory(MicroscopeFactory):
    def __init__(self) -> None:
        self._instrument = None
        self._microscope = None

    def is_available(self) -> bool:
        try:
            import temscript  # noqa: F401
        except ImportError:
            logger.warning("temscript module not available")
            return False
        return True

    def create_microscope(self) -> MicroscopeInterface:
        if not self.is_available():
            raise MicroscopeFactoryError("temscript not available")

        try:
            import temscript

            self._instrument = temscript.GetInstrument()
            if not validate_temscript_connection(self._instrument):
                raise MicroscopeConnectionError(
                    "Failed to connect to local microscope"
                )
            self._microscope = create_temscript_microscope(self._instrument)
            logger.info("Local temscript microscope created successfully")
            return self._microscope
        except Exception as exc:
            logger.error("Failed to create local microscope: %s", exc)
            raise MicroscopeFactoryError(
                f"Failed to create local microscope: {exc}"
            ) from exc

    def get_info(self) -> dict[str, Any]:
        if not self._instrument:
            return {"type": "local", "status": "not_connected"}

        try:
            config = self._instrument.Configuration
            return {
                "type": "local",
                "status": "connected",
                "product_family": str(config.ProductFamily),
                "connection_type": "direct_temscript",
            }
        except Exception as exc:
            logger.warning("Failed to get local microscope info: %s", exc)
            return {
                "type": "local",
                "status": "connected",
                "info_error": str(exc),
            }


class RemoteTemscriptFactory(MicroscopeFactory):
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url
        self._microscope = None

    def is_available(self) -> bool:
        # Network probing is deliberately not implemented yet.
        return True

    def create_microscope(self) -> MicroscopeInterface:
        try:
            raise NotImplementedError("Remote microscope connection not yet implemented")
        except Exception as exc:
            logger.error("Failed to create remote microscope: %s", exc)
            raise MicroscopeFactoryError(
                f"Failed to create remote microscope: {exc}"
            ) from exc

    def get_info(self) -> dict[str, Any]:
        return {
            "type": "remote",
            "status": "not_implemented",
            "server_url": self.server_url,
            "connection_type": "remote_temscript_server",
        }


class NullMicroscopeFactory(MicroscopeFactory):
    def __init__(self) -> None:
        self._microscope = None

    def is_available(self) -> bool:
        return True

    def create_microscope(self) -> MicroscopeInterface:
        try:
            self._microscope = NullMicroscope()
            logger.info("Null microscope simulator created successfully")
            return self._microscope
        except Exception as exc:
            logger.error("Failed to create null microscope: %s", exc)
            raise MicroscopeFactoryError(
                f"Failed to create null microscope: {exc}"
            ) from exc

    def get_info(self) -> dict[str, Any]:
        return {
            "type": "null",
            "status": "available",
            "connection_type": "simulator",
            "description": "Null microscope simulator for testing",
        }


class MicroscopeWiring:
    """Own the selected factory, microscope implementation, and aggregate."""

    def __init__(self, mode: str = "local", server_url: str | None = None) -> None:
        self.mode = mode
        self.server_url = server_url
        self.factory = self._create_factory()
        self.microscope: Optional[MicroscopeInterface] = None
        self.aggregate: Optional[MicroscopeAggregate] = None

    def _create_factory(self) -> MicroscopeFactory:
        if self.mode == "local":
            logger.info("LocalTemscriptFactory created")
            return LocalTemscriptFactory()
        if self.mode == "remote":
            if not self.server_url:
                raise MicroscopeFactoryError("Server URL required for remote mode")
            logger.info("RemoteTemscriptFactory created")
            return RemoteTemscriptFactory(self.server_url)
        if self.mode == "null":
            logger.info("NullMicroscopeFactory created")
            return NullMicroscopeFactory()
        raise MicroscopeFactoryError(f"Unknown mode: {self.mode}")

    def connect(self) -> bool:
        try:
            if not self.factory.is_available():
                logger.error("Microscope factory %s is not available", self.mode)
                return False
            self.microscope = self.factory.create_microscope()
            self.aggregate = MicroscopeAggregate(self.microscope)
            logger.info("Successfully connected to %s microscope", self.mode)
            return True
        except Exception as exc:
            logger.error("Failed to connect to microscope: %s", exc)
            return False

    def disconnect(self) -> None:
        # Preserve legacy behavior until real-hardware lifecycle handling can be
        # tested: only hardware objects exposing ``instrument`` are cleared.
        if self.microscope and hasattr(self.microscope, "instrument"):
            try:
                self.microscope = None
                self.aggregate = None
                logger.info("Microscope disconnected")
            except Exception as exc:
                logger.warning("Error during disconnect: %s", exc)

    def is_connected(self) -> bool:
        if self.microscope is None or self.aggregate is None:
            return False
        try:
            return self.microscope.is_connected()
        except Exception as exc:
            logger.error("Error checking connection: %s", exc)
            return False

    def get_microscope(self) -> Optional[MicroscopeInterface]:
        return self.microscope

    def get_aggregate(self) -> Optional[MicroscopeAggregate]:
        return self.aggregate

    def get_info(self) -> dict[str, Any]:
        info = self.factory.get_info()
        info.update({"mode": self.mode, "connected": self.is_connected()})
        return info

    def get_snapshot(self) -> Optional[MicroscopeState]:
        if not self.is_connected():
            logger.warning("Microscope not connected")
            return None
        try:
            return self.aggregate.get_snapshot() if self.aggregate else None
        except Exception as exc:
            logger.error("Failed to get snapshot: %s", exc)
            return None

    def set_component_params(self, component: str, params: Any) -> bool:
        if not self.is_connected():
            logger.warning("Microscope not connected")
            return False
        try:
            if self.aggregate is None:
                return False
            return self.aggregate.set_component_params(component, params)
        except Exception as exc:
            logger.error("Error setting component params: %s", exc)
            return False

    def execute_command(self, component: str, command: str, **kwargs: Any) -> bool:
        if not self.is_connected():
            logger.warning("Microscope not connected")
            return False
        try:
            if self.aggregate is None:
                return False
            return self.aggregate.execute_command(component, command, **kwargs)
        except Exception as exc:
            logger.error("Failed to execute command: %s", exc)
            return False


def create_microscope_wiring(
    mode: str = "local", server_url: str | None = None
) -> MicroscopeWiring:
    return MicroscopeWiring(mode, server_url)


def get_available_modes() -> dict[str, bool]:
    return {
        "local": LocalTemscriptFactory().is_available(),
        "null": True,
        "remote": False,
    }


def validate_mode(mode: str) -> bool:
    available_modes = get_available_modes()
    return mode in available_modes and available_modes[mode]


def get_default_mode() -> str:
    return os.getenv("ZHOUTOMO_MODE", "local")


def get_default_server_url() -> str:
    return os.getenv("ZHOUTOMO_SERVER_URL", "")


def create_default_wiring() -> MicroscopeWiring:
    mode = get_default_mode()
    server_url = get_default_server_url() if mode == "remote" else None
    return create_microscope_wiring(mode, server_url)


def create_local_wiring() -> MicroscopeWiring:
    return create_microscope_wiring("local")


def create_null_wiring() -> MicroscopeWiring:
    return create_microscope_wiring("null")


def create_remote_wiring(server_url: str) -> MicroscopeWiring:
    return create_microscope_wiring("remote", server_url)
