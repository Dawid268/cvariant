from typing import Literal

from app.core.schemas import CamelModel


class HealthResponse(CamelModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(CamelModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]
