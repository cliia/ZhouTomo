"""Serialization helpers for the shared protocol models."""

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from .models import MicroscopeParams, MicroscopeState


def _to_primitive(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_primitive(item) for item in value]
    return value


def state_to_dict(state: MicroscopeState) -> dict[str, Any]:
    return _to_primitive(state)


def params_to_dict(params: MicroscopeParams) -> dict[str, Any]:
    return _to_primitive(params)


def create_default_state() -> MicroscopeState:
    return MicroscopeState()


def create_default_params() -> MicroscopeParams:
    return MicroscopeParams()
