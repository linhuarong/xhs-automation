from typing import Any, Literal

from pydantic import BaseModel, Field


class YingdaoHandoffInstruction(BaseModel):
    """Instructions for the future Yingdao local file reader."""

    rpa_should_read_this_file: bool = True
    rpa_should_write_evidence_json: bool = True
    do_not_bypass_login_or_verification: bool = True
    do_not_click_final_publish_without_manual_review: bool | None = None


class YingdaoSearchActiveJob(BaseModel):
    """Stable active search job contract for Yingdao local file handoff."""

    schema_version: str = "1.0"
    job_type: Literal["xhs_search"] = "xhs_search"
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_file_trigger"
    created_at: str
    status: str = "pending_rpa_pickup"
    keyword: str
    limit: int = 20
    capture_screenshot: bool = True
    evidence_output_dir: str
    expected_evidence_file: str = "search_evidence.json"
    safe_mode: bool = True
    instructions: YingdaoHandoffInstruction = Field(default_factory=YingdaoHandoffInstruction)


class YingdaoPublishActiveJob(BaseModel):
    """Stable active publish job contract for Yingdao local file handoff."""

    schema_version: str = "1.0"
    job_type: Literal["xhs_publish"] = "xhs_publish"
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_file_trigger"
    created_at: str
    status: str = "pending_rpa_pickup"
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    tags_json: str = "[]"
    image_paths: list[str] = Field(default_factory=list)
    image_paths_json: str = "[]"
    publish_mode: str = "manual_review"
    evidence_output_dir: str
    expected_evidence_file: str = "publish_evidence.json"
    safe_mode: bool = True
    instructions: YingdaoHandoffInstruction = Field(
        default_factory=lambda: YingdaoHandoffInstruction(
            do_not_click_final_publish_without_manual_review=True
        )
    )


class YingdaoHandoffManifest(BaseModel):
    """Manifest written next to each local handoff job snapshot."""

    schema_version: str = "1.0"
    job_type: Literal["xhs_search", "xhs_publish"]
    job_id: str
    active_job_path: str
    job_snapshot_path: str
    expected_evidence_path: str
    created_at: str
    safe_mode: bool = True


class YingdaoHandoffResult(BaseModel):
    """Result returned after preparing a local Yingdao handoff."""

    job_id: str
    status: str
    message: str | None = None
    active_job_path: str
    job_dir: str
    manifest_path: str
    expected_evidence_path: str
    error_code: str | None = None
    error_message: str | None = None


class YingdaoEvidenceReadResult(BaseModel):
    """Result returned after reading local Yingdao evidence."""

    job_id: str
    job_type: Literal["xhs_search", "xhs_publish"]
    status: str
    message: str | None = None
    evidence_json_path: str | None = None
    evidence: dict[str, Any] | None = None
    worker_result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
