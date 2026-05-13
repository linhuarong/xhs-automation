from typing import Any, Literal

from pydantic import BaseModel, Field


XhsN8nDispatchJobType = Literal["search", "publish", "full"]
XhsN8nDispatchStepName = Literal[
    "search",
    "publish",
    "postgres_persistence",
    "minio_storage",
    "feishu_write",
    "feishu_readback",
    "full_dry_run",
]


class XhsN8nDispatchRequest(BaseModel):
    """Request for local n8n-style browser-worker dry-run dispatch smoke."""

    job_id: str
    job_type: XhsN8nDispatchJobType
    account_id: str
    trigger_source: str = "n8n_smoke"
    dry_run: bool = True
    steps: list[XhsN8nDispatchStepName] | None = None
    payload: dict[str, Any] | None = None
    base_url: str = "http://127.0.0.1:8000"


class XhsN8nDispatchStep(BaseModel):
    """One local dry-run dispatch step."""

    step_name: XhsN8nDispatchStepName
    status: str
    dry_run: bool = True
    local_route: str | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    summary_path: str | None = None
    external_calls_made: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsN8nDispatchResult(BaseModel):
    """Result for local n8n-style dry-run dispatch smoke."""

    schema_version: str = "1.0"
    result_type: str = "local_n8n_dispatch_smoke_result"
    job_id: str
    job_type: XhsN8nDispatchJobType
    account_id: str
    status: str
    trigger_source: str = "n8n_smoke"
    dry_run: bool = True
    steps: list[XhsN8nDispatchStep] = Field(default_factory=list)
    request_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    external_calls_made: bool = False
    sensitive_payload_detected: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsN8nDispatchSummary(BaseModel):
    """Summary for local n8n-style dry-run dispatch smoke."""

    schema_version: str = "1.0"
    summary_type: str = "local_n8n_dispatch_smoke_summary"
    job_id: str
    job_type: XhsN8nDispatchJobType
    account_id: str
    status: str
    dry_run: bool = True
    step_count: int = 0
    successful_step_count: int = 0
    failed_step_count: int = 0
    request_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    generated_outputs: list[str] = Field(default_factory=list)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)
    sensitive_scan: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    error_code: str | None = None
    error_message: str | None = None
