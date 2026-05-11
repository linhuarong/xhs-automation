from typing import Any, Literal

from pydantic import BaseModel, Field


XhsE2EReplayJobType = Literal["search", "publish", "all"]


class XhsE2EReplayRequest(BaseModel):
    """Request for local full E2E replay orchestration."""

    run_id: str
    job_type: XhsE2EReplayJobType
    account_id: str
    search_job_id: str | None = None
    publish_job_id: str | None = None
    keyword: str | None = None
    limit: int = 20
    title: str | None = None
    body: str | None = None
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"
    strict_mode: bool = True
    dry_run: bool = True


class XhsE2EReplayStepResult(BaseModel):
    """One local E2E replay step result."""

    step_name: str
    status: str
    input_path: str | None = None
    output_path: str | None = None
    summary_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsE2EReplayResult(BaseModel):
    """Local full E2E replay result."""

    schema_version: str = "1.0"
    replay_type: str = "local_full_e2e_replay"
    run_id: str
    job_type: XhsE2EReplayJobType
    status: str
    steps: list[XhsE2EReplayStepResult] = Field(default_factory=list)
    e2e_input_path: str
    e2e_result_path: str
    e2e_summary_path: str
    artifacts_manifest_path: str
    sensitive_payload_detected: bool = False
    external_call_forbidden: bool = True
    error_code: str | None = None
    error_message: str | None = None


class XhsE2EReplaySummary(BaseModel):
    """Local full E2E replay summary."""

    schema_version: str = "1.0"
    summary_type: str = "local_full_e2e_replay_summary"
    run_id: str
    job_type: XhsE2EReplayJobType
    status: str
    readiness_status: str | None = None
    strict_binding_status: str | None = None
    hardened_discovery_status: str | None = None
    contract_replay_status: str | None = None
    persistence_replay_status: str | None = None
    generated_artifacts: list[str] = Field(default_factory=list)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)
    sensitive_scan: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    error_code: str | None = None
    error_message: str | None = None
