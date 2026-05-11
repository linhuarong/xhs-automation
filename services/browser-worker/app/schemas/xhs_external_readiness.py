from typing import Any

from pydantic import BaseModel, Field


class ExternalDependencyStatus(BaseModel):
    """One external dependency readiness status."""

    name: str
    mode: str
    status: str
    required: bool = False
    message: str | None = None
    checks: dict[str, bool | str | int | None] = Field(default_factory=dict)


class ExternalReadinessSummary(BaseModel):
    """Aggregated external readiness counts."""

    total: int = 0
    ready: int = 0
    mock_ready: int = 0
    disabled: int = 0
    missing_config: int = 0
    failed: int = 0


class ExternalReadinessResult(BaseModel):
    """Full external readiness result."""

    status: str
    safe_mode: bool
    environment: str
    summary: ExternalReadinessSummary
    dependencies: list[ExternalDependencyStatus] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
