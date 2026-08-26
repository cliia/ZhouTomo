"""Server-side domain interfaces and aggregate.

Shared state/parameter dataclasses live in :mod:`zhoutomo_protocol`.
"""

import logging
from typing import Any

from zhoutomo_protocol import *

logger = logging.getLogger(__name__)


class MicroscopeInterface:
    def get_state(self) -> MicroscopeState:
        raise NotImplementedError

    def set_params(self, params: MicroscopeParams) -> bool:
        raise NotImplementedError

    def get_component_state(self, component: str) -> Any:
        raise NotImplementedError

    def set_component_params(self, component: str, params: Any) -> bool:
        raise NotImplementedError

    def execute_command(self, component: str, command: str, **kwargs: Any) -> bool:
        raise NotImplementedError

    def start_acquisition(self) -> bool:
        raise NotImplementedError

    def stop_acquisition(self) -> bool:
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError


class MicroscopeAggregate:
    """Aggregate root around one concrete microscope implementation."""

    def __init__(self, microscope: MicroscopeInterface):
        self.microscope = microscope
        if hasattr(microscope, "_components"):
            self._components = microscope._components
        else:
            names = (
                "gun",
                "illumination",
                "projection",
                "stage",
                "vacuum",
                "mode",
                "blanker",
                "camera",
                "acquisition",
                "auto_normalize",
            )
            self._components = {name: getattr(microscope, name, None) for name in names}

    def get_snapshot(self) -> MicroscopeState:
        return self.microscope.get_state()

    def get_component_state(self, component: str) -> Any:
        self._require_component(component)
        return self.microscope.get_component_state(component)

    def set_component_params(self, component: str, params: Any) -> bool:
        self._require_component(component)
        return self.microscope.set_component_params(component, params)

    def execute_command(self, component: str, command: str, **kwargs: Any) -> bool:
        self._require_component(component)
        return self.microscope.execute_command(component, command, **kwargs)

    def list_components(self) -> list[str]:
        return list(self._components)

    def has_component(self, component: str) -> bool:
        return component in self._components

    def get_available_components(self) -> list[str]:
        return [name for name, implementation in self._components.items() if implementation is not None]

    def _require_component(self, component: str) -> None:
        if component not in self._components:
            raise ValueError(f"Unknown component: {component}")


def validate_params(params: MicroscopeParams) -> list[str]:
    """Validate fields that currently expose explicit limits."""

    errors: list[str] = []
    projection = params.projection
    if not projection.min_magnification <= projection.magnification <= projection.max_magnification:
        errors.append(
            "Projection magnification must be between "
            f"{projection.min_magnification} and {projection.max_magnification}"
        )
    return errors
