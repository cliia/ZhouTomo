"""Stable error identifiers for the ZhouTomo wire protocol."""

from enum import Enum


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "invalid_argument"
    DEVICE_BUSY = "device_busy"
    HARDWARE_ERROR = "hardware_error"
    NOT_CONNECTED = "not_connected"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"
