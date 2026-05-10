from typing import Literal

from pydantic import BaseModel, Field


class XhsPublishAsset(BaseModel):
    """One asset used by an XHS publish job."""

    asset_id: str | None = None
    local_path: str | None = None
    source_url: str | None = None
    minio_url: str | None = None
    feishu_file_token: str | None = None
    order: int | None = None
    asset_type: Literal["image", "video"] = "image"
    caption: str | None = None
    checksum: str | None = None


class XhsPublishJob(BaseModel):
    """Payload for a local-file-trigger XHS publish job."""

    job_id: str
    task_type: str = "xhs_publish_note"
    account_id: str
    provider_type: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    assets: list[XhsPublishAsset] = Field(default_factory=list)
    visibility: str | None = None
    scheduled_at: str | None = None
    source_record_id: str | None = None
    output_dir: str | None = None


class XhsPublishEvidence(BaseModel):
    """Evidence JSON emitted by local publish RPA."""

    job_id: str | None = None
    task_type: str | None = "xhs_publish_note"
    status: str | None = None
    account_id: str | None = None
    provider_type: str | None = None
    title: str | None = None
    note_url: str | None = None
    note_id: str | None = None
    published_at: str | None = None
    screenshot_path: str | None = None
    evidence_json_path: str | None = None
    before_publish_screenshot_path: str | None = None
    form_filled_screenshot_path: str | None = None
    result_screenshot_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw: dict = Field(default_factory=dict)


class XhsPublishResult(BaseModel):
    """Result returned by the browser-worker publish API."""

    job_id: str
    status: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    note_url: str | None = None
    note_id: str | None = None
    evidence_json_path: str | None = None
    screenshot_url: str | None = None
    published_at: str | None = None


class XhsBatchPublishRequest(BaseModel):
    """Batch publish request."""

    batch_id: str
    account_id: str
    provider_type: str
    jobs: list[XhsPublishJob]
    mode: Literal["sync", "async"] = "sync"


class XhsBatchPublishResult(BaseModel):
    """Batch publish summary."""

    batch_id: str
    status: str
    total_jobs: int
    success_count: int
    failed_count: int
    jobs: list[dict] = Field(default_factory=list)
    created_at: str
    finished_at: str | None = None
