"""Microscope application service.

This module contains transport-independent orchestration around the aggregate.
Hardware SDK access remains behind the existing wiring/driver implementation.
"""

from typing import Any

from zhoutomo_protocol import AcquisitionParams, state_to_dict


class MicroscopeService:
    def __init__(self, aggregate) -> None:
        self.aggregate = aggregate

    def get_snapshot(self) -> dict[str, Any]:
        return state_to_dict(self.aggregate.get_snapshot())

    def list_components(self) -> list[str]:
        return self.aggregate.get_available_components()

    def get_component_state(self, component: str) -> dict[str, Any]:
        if not self.aggregate.has_component(component):
            raise KeyError(component)
        return state_to_dict(self.aggregate.get_component_state(component))

    def get_parameter_schema(self) -> dict[str, Any]:
        """Return the legacy configurable-parameter description unchanged."""
        return {
            "camera": {
                "exposure_time": {"min": 0.1, "max": 1000.0, "default": 100.0},
                "gain": {"min": 0.1, "max": 10.0, "default": 1.0},
            },
            "stage": {
                "x": {"min": -1000, "max": 1000, "default": 0},
                "y": {"min": -1000, "max": 1000, "default": 0},
            },
        }

    def set_component_params(self, component: str, params: dict[str, Any]) -> bool:
        if not self.aggregate.has_component(component):
            raise KeyError(component)

        converted: Any = params
        if component == "acquisition":
            allowed = {
                "acq_image_size",
                "dwell_time",
                "brightness",
                "contrast",
                "binnings",
                "frames",
            }
            converted = AcquisitionParams(**{key: value for key, value in params.items() if key in allowed})

        return bool(self.aggregate.set_component_params(component, converted))

    def execute_command(self, component: str, command: str, parameters: dict[str, Any]) -> Any:
        if not self.aggregate.has_component(component):
            raise KeyError(component)
        return self.aggregate.execute_command(component, command, **parameters)
