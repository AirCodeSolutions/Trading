from datetime import datetime

from pydantic import BaseModel, Field


class RuntimeDrainState(BaseModel):
    enabled: bool = False
    updated_at: datetime | None = None
    reason: str = Field(default="", max_length=240)


class RuntimeDrainRequest(BaseModel):
    enabled: bool
    reason: str = Field(default="", max_length=240)
