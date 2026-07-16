"""RFC 7807 ("problem+json") error envelope, used by every error response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    type: str = Field(description="A short machine-readable error code, e.g. 'not_found'")
    title: str = Field(description="Short human-readable summary of the problem")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation specific to this occurrence")
    trace_id: str | None = Field(default=None, description="Correlation id, echoed in X-Request-ID")
