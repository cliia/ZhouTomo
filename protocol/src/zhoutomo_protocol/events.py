"""WebSocket event envelopes shared by client and server."""

from typing import Any

from pydantic import BaseModel, Field


class Event(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class FrameEvent(BaseModel):
    type: str = "frame"
    data: dict[str, Any] = Field(default_factory=dict)
