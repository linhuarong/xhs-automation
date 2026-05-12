from typing import Literal

from pydantic import BaseModel, Field


XhsMinioStorageJobType = Literal["search", "publish"]
XhsMinioArtifactType = Literal[
    "evidence_json",
    "screenshot",
    "manifest",
    "publish_asset",
    "error_json",
    "other",
]


class XhsMinioUploadSource(BaseModel):
    """Source artifact for controlled MinIO upload planning."""

    source_path: str
    logical_name: str | None = None
    artifact_type: XhsMinioArtifactType = "other"
    required: bool = True


class XhsMinioStorageRequest(BaseModel):
    """Request for MinIO storage phase 1."""

    job_id: str
    job_type: XhsMinioStorageJobType
    account_id: str
    provider_type: str | None = None
    evidence_dir: str | None = None
    sources: list[XhsMinioUploadSource] | None = None
    dry_run: bool = True
    overwrite: bool = False
    include_optional_missing: bool = True
    object_prefix: str | None = None


class XhsMinioUploadPlanItem(BaseModel):
    """One planned object upload."""

    source_path: str
    exists: bool
    required: bool = True
    artifact_type: XhsMinioArtifactType = "other"
    size_bytes: int | None = None
    sha256: str | None = None
    object_key: str | None = None
    content_type: str | None = None
    upload_allowed: bool = False
    skip_reason: str | None = None


class XhsMinioUploadPlan(BaseModel):
    """Upload plan written before any real MinIO action."""

    schema_version: str = "1.0"
    plan_type: str = "controlled_minio_upload_plan"
    job_id: str
    job_type: XhsMinioStorageJobType
    account_id: str
    bucket: str | None = None
    dry_run: bool = True
    upload_enabled: bool = False
    real_upload_allowed: bool = False
    items: list[XhsMinioUploadPlanItem] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class XhsMinioUploadResultItem(BaseModel):
    """Result for one planned MinIO object."""

    source_path: str
    object_key: str | None = None
    bucket: str | None = None
    uploaded: bool = False
    dry_run: bool = True
    public_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsMinioUploadResult(BaseModel):
    """Result for controlled MinIO storage phase 1."""

    schema_version: str = "1.0"
    result_type: str = "controlled_minio_upload_result"
    job_id: str
    job_type: XhsMinioStorageJobType
    account_id: str
    status: str
    dry_run: bool = True
    bucket: str | None = None
    upload_enabled: bool = False
    real_upload_allowed: bool = False
    uploaded_count: int = 0
    skipped_count: int = 0
    plan_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    items: list[XhsMinioUploadResultItem] = Field(default_factory=list)
    sensitive_file_detected: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsMinioUploadSummary(BaseModel):
    """Summary for controlled MinIO storage phase 1."""

    schema_version: str = "1.0"
    summary_type: str = "controlled_minio_upload_summary"
    job_id: str
    job_type: XhsMinioStorageJobType
    total_sources: int = 0
    existing_sources: int = 0
    missing_sources: int = 0
    planned_uploads: int = 0
    uploaded_count: int = 0
    skipped_count: int = 0
    dry_run: bool = True
    upload_enabled: bool = False
    real_upload_allowed: bool = False
    manifest_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    sensitive_scan: dict = Field(default_factory=dict)
    created_at: str
    error_code: str | None = None
    error_message: str | None = None
