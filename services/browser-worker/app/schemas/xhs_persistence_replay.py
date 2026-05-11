from typing import Any, Literal

from pydantic import BaseModel, Field


XhsPersistenceTarget = Literal["feishu", "postgres", "minio", "all"]
XhsPersistenceJobType = Literal["search", "publish"]


class XhsPersistenceReplayRequest(BaseModel):
    """Generic local mock persistence replay request."""

    job_id: str
    job_type: XhsPersistenceJobType
    account_id: str
    source_replay_result_path: str | None = None
    source_replay_summary_path: str | None = None
    strict_mode: bool = True
    dry_run: bool = True


class XhsFeishuMockPersistencePayload(BaseModel):
    """Local-only Feishu mock persistence payload."""

    schema_version: str = "1.0"
    persistence_type: Literal["local_feishu_mock_persistence"] = "local_feishu_mock_persistence"
    job_id: str
    job_type: XhsPersistenceJobType
    account_id: str
    feishu_record_id: str | None = None
    target_table: str
    operation: str = "mock_update_record"
    fields: dict[str, Any] = Field(default_factory=dict)
    strict_binding_context: dict[str, Any] = Field(default_factory=dict)
    hardened_discovery_reference: dict[str, Any] = Field(default_factory=dict)
    source_replay_reference: dict[str, Any] = Field(default_factory=dict)
    forbidden_external_write: bool = True


class XhsPostgresMockPersistencePayload(BaseModel):
    """Local-only PostgreSQL mock persistence payload."""

    schema_version: str = "1.0"
    persistence_type: Literal["local_postgres_mock_persistence"] = "local_postgres_mock_persistence"
    job_id: str
    job_type: XhsPersistenceJobType
    account_id: str
    target_tables: list[str] = Field(default_factory=list)
    operation_plan: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    strict_binding_context: dict[str, Any] = Field(default_factory=dict)
    hardened_discovery_reference: dict[str, Any] = Field(default_factory=dict)
    source_replay_reference: dict[str, Any] = Field(default_factory=dict)
    forbidden_external_write: bool = True


class XhsMinioMockObjectManifest(BaseModel):
    """Local-only MinIO mock object manifest."""

    schema_version: str = "1.0"
    persistence_type: Literal["local_minio_mock_object_manifest"] = "local_minio_mock_object_manifest"
    job_id: str
    job_type: XhsPersistenceJobType
    account_id: str
    bucket: str = "xhs-assets-mock"
    object_prefix: str
    objects: list[dict[str, Any]] = Field(default_factory=list)
    strict_binding_context: dict[str, Any] = Field(default_factory=dict)
    hardened_discovery_reference: dict[str, Any] = Field(default_factory=dict)
    source_replay_reference: dict[str, Any] = Field(default_factory=dict)
    forbidden_external_upload: bool = True


class XhsPersistenceReplayResult(BaseModel):
    """Result for one local mock persistence replay target."""

    schema_version: str = "1.0"
    result_type: str = "local_persistence_replay_result"
    job_id: str
    job_type: XhsPersistenceJobType
    target: XhsPersistenceTarget
    status: str
    payload_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    sensitive_payload_detected: bool = False
    external_write_forbidden: bool = True
    strict_binding_status: str | None = None
    hardened_discovery_status: str | None = None
    source_replay_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsPersistenceReplaySummary(BaseModel):
    """Summary for local mock persistence replay."""

    schema_version: str = "1.0"
    summary_type: str = "local_persistence_replay_summary"
    job_id: str
    job_type: XhsPersistenceJobType
    targets: list[XhsPersistenceTarget] = Field(default_factory=list)
    status: str
    strict_binding_status: str | None = None
    hardened_discovery_status: str | None = None
    source_replay_status: str | None = None
    generated_payloads: list[str] = Field(default_factory=list)
    generated_results: list[str] = Field(default_factory=list)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)
    sensitive_scan: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    error_code: str | None = None
    error_message: str | None = None


class XhsPersistenceReplayAllResult(BaseModel):
    """Result for feishu/postgres/minio local persistence replay."""

    schema_version: str = "1.0"
    result_type: str = "local_persistence_replay_all_result"
    job_id: str
    job_type: XhsPersistenceJobType
    status: str
    feishu: dict[str, Any] | None = None
    postgres: dict[str, Any] | None = None
    minio: dict[str, Any] | None = None
    result_path: str | None = None
    summary_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
