"""Transport-level request and response schemas shared by client and server."""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    microscope_connected: bool
    uptime: float


class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: str
    request_id: str


class ComponentParamsRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class CommandRequest(BaseModel):
    parameters: dict[str, Any] | None = None


class CommandResponse(BaseModel):
    success: bool
    message: str
    timestamp: str


class FrameData(BaseModel):
    frame_id: str
    timestamp: float
    component: str
    data: bytes = b""
    metadata: dict[str, Any] = Field(default_factory=dict)
