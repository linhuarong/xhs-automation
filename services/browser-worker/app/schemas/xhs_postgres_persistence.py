from typing import Any, Literal

from pydantic import BaseModel, Field


XhsPostgresPersistenceJobType = Literal["search", "publish"]


class XhsPostgresPersistenceRequest(BaseModel):
    """Request for controlled PostgreSQL persistence from local replay payload."""

    job_id: str
    job_type: XhsPostgresPersistenceJobType
    account_id: str
    persistence_payload_path: str | None = None
    dry_run: bool = True
    require_safe_payload: bool = True


class XhsPostgresPersistenceResult(BaseModel):
    """Result for PostgreSQL persistence phase 1."""

    schema_version: str = "1.0"
    result_type: str = "controlled_postgres_persistence_result"
    job_id: str
    job_type: XhsPostgresPersistenceJobType
    account_id: str
    status: str
    dry_run: bool = True
    rows_planned: int = 0
    rows_written: int = 0
    target_tables: list[str] = Field(default_factory=list)
    payload_path: str | None = None
    plan_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    sensitive_payload_detected: bool = False
    postgres_write_enabled: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsPostgresPersistenceSummary(BaseModel):
    """Summary for PostgreSQL persistence phase 1."""

    schema_version: str = "1.0"
    summary_type: str = "controlled_postgres_persistence_summary"
    job_id: str
    job_type: XhsPostgresPersistenceJobType
    status: str
    dry_run: bool = True
    target_tables: list[str] = Field(default_factory=list)
    rows_planned: int = 0
    rows_written: int = 0
    summary_path: str | None = None
    created_at: str
    payload_scan: dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
