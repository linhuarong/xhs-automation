from typing import Any, Literal

from pydantic import BaseModel, Field


YingdaoSmokeJobType = Literal["xhs_search", "xhs_publish"]
YingdaoSmokeStatus = Literal[
    "prepared",
    "waiting_desktop_rpa",
    "rpa_file_read_success",
    "evidence_written",
    "verified",
    "failed",
]


class YingdaoSmokeRuntimeInfo(BaseModel):
    """Runtime safety flags reported by the manual Yingdao desktop smoke flow."""

    tool: str = "yingdao_desktop"
    mode: str = "manual_smoke"
    opened_browser: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False


class YingdaoSmokeReceipt(BaseModel):
    """Receipt written by Yingdao desktop after reading an active job file."""

    schema_version: str = "1.0"
    smoke_type: str = "yingdao_desktop_manual_file_read"
    job_type: YingdaoSmokeJobType
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_file_trigger"
    status: str = "rpa_file_read_success"
    read_at: str
    source_active_job_path: str
    evidence_output_dir: str
    rpa_runtime: YingdaoSmokeRuntimeInfo = Field(default_factory=YingdaoSmokeRuntimeInfo)
    message: str = "Yingdao desktop RPA read active job file and wrote receipt locally."


class YingdaoSmokePrepareRequest(BaseModel):
    """Prepare request for a desktop smoke run."""

    job_id: str
    account_id: str
    job_type: Literal["search", "publish"] = "search"
    keyword: str | None = None
    limit: int = 20
    title: str | None = None
    body: str | None = None
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)


class YingdaoSmokePrepareResult(BaseModel):
    """Result returned after preparing a manual desktop smoke run."""

    job_id: str
    job_type: YingdaoSmokeJobType
    status: str
    active_job_path: str
    smoke_dir: str
    expected_receipt_path: str
    expected_evidence_path: str
    active_job_snapshot_path: str | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class YingdaoSmokeSummary(BaseModel):
    """Safety summary for a desktop smoke verification."""

    receipt_exists: bool = False
    evidence_exists: bool = False
    receipt_valid: bool = False
    evidence_valid: bool = False
    opened_browser: bool = False
    opened_xhs: bool = False
    real_action_executed: bool = False


class YingdaoSmokeVerifyResult(BaseModel):
    """Verification result for a manual desktop smoke run."""

    job_id: str
    job_type: YingdaoSmokeJobType
    status: str
    receipt_path: str
    evidence_path: str
    smoke_summary_path: str
    summary: YingdaoSmokeSummary = Field(default_factory=YingdaoSmokeSummary)
    receipt: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
