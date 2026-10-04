"""`GET /api/health` response body (R12.6, design.md §8.3).

This is the one endpoint that never uses the error envelope: both 200 and 503 return `Health`.
"""

from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class DatabaseStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


class HealthResponse(BaseModel):
    status: HealthStatus
    database: DatabaseStatus
    version: str
