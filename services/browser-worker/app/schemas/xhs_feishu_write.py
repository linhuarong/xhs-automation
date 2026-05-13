from typing import Any, Literal

from pydantic import BaseModel, Field


XhsFeishuJobType = Literal["search", "publish"]
XhsFeishuRecordOperation = Literal["create", "update", "upsert_plan_only"]
XhsFeishuReadbackOperation = Literal["create", "update", "readback"]


class XhsFeishuFieldMapping(BaseModel):
    """Optional source-to-Feishu field mapping override."""

    source_field: str
    feishu_field: str


class XhsFeishuWriteRequest(BaseModel):
    """Request for controlled Feishu write planning or explicit write."""

    job_id: str
    job_type: XhsFeishuJobType
    account_id: str | None = None
    operation: XhsFeishuRecordOperation = "upsert_plan_only"
    feishu_record_id: str | None = None
    source_result_path: str | None = None
    source_summary_path: str | None = None
    records: list[dict[str, Any]] | None = None
    dry_run: bool = True
    table_id: str | None = None
    app_token: str | None = None
    field_mapping: dict[str, str] | None = None
    include_raw_payload: bool = True


class XhsFeishuWritePlanItem(BaseModel):
    """One planned Feishu record mutation."""

    operation: XhsFeishuRecordOperation
    record_id: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    write_allowed: bool = False
    skip_reason: str | None = None


class XhsFeishuWritePlan(BaseModel):
    """Feishu write plan. It never contains app secrets or tokens."""

    schema_version: str = "1.0"
    plan_type: str = "controlled_feishu_write_plan"
    job_id: str
    job_type: XhsFeishuJobType
    operation: XhsFeishuRecordOperation
    dry_run: bool = True
    target_table_kind: str
    write_enabled: bool = False
    real_write_allowed: bool = False
    app_token_configured: bool = False
    table_id_configured: bool = False
    items: list[XhsFeishuWritePlanItem] = Field(default_factory=list)
    source_result_path: str | None = None
    source_summary_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsFeishuWritePayload(BaseModel):
    """Feishu API-shaped payload without app token, table id, or credentials."""

    schema_version: str = "1.0"
    payload_type: str = "controlled_feishu_write_payload"
    job_id: str
    job_type: XhsFeishuJobType
    operation: XhsFeishuRecordOperation
    target_table_kind: str
    records: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_external_write: bool = True


class XhsFeishuWriteResult(BaseModel):
    """Result for controlled Feishu write phase 1."""

    schema_version: str = "1.0"
    result_type: str = "controlled_feishu_write_result"
    job_id: str
    job_type: XhsFeishuJobType
    account_id: str | None = None
    status: str
    operation: XhsFeishuRecordOperation
    dry_run: bool = True
    write_enabled: bool = False
    real_write_allowed: bool = False
    target_table_kind: str
    record_count: int = 0
    planned_create_count: int = 0
    planned_update_count: int = 0
    written_count: int = 0
    skipped_count: int = 0
    record_id: str | None = None
    plan_path: str | None = None
    payload_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    sensitive_payload_detected: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsFeishuWriteSummary(BaseModel):
    """Summary for controlled Feishu write phase 1."""

    schema_version: str = "1.0"
    summary_type: str = "controlled_feishu_write_summary"
    job_id: str
    job_type: XhsFeishuJobType
    operation: XhsFeishuRecordOperation
    dry_run: bool = True
    write_enabled: bool = False
    real_write_allowed: bool = False
    target_table_kind: str
    record_count: int = 0
    planned_create_count: int = 0
    planned_update_count: int = 0
    written_count: int = 0
    skipped_count: int = 0
    record_id: str | None = None
    plan_path: str | None = None
    payload_path: str | None = None
    result_path: str | None = None
    summary_path: str | None = None
    payload_scan: dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)
    created_at: str
    error_code: str | None = None
    error_message: str | None = None


class XhsFeishuReadbackRequest(BaseModel):
    """Request for controlled single-record Feishu readback checking."""

    job_id: str
    job_type: XhsFeishuJobType
    account_id: str | None = None
    operation: XhsFeishuReadbackOperation = "readback"
    feishu_record_id: str | None = None
    records: list[dict[str, Any]] | None = None
    dry_run: bool = True
    table_id: str | None = None
    app_token: str | None = None
    field_mapping: dict[str, str] | None = None


class XhsFeishuReadbackCheck(BaseModel):
    """Expected-vs-actual Feishu field comparison."""

    schema_version: str = "1.0"
    check_type: str = "controlled_feishu_readback_check"
    job_id: str
    job_type: XhsFeishuJobType
    operation: XhsFeishuReadbackOperation
    dry_run: bool = True
    record_id: str | None = None
    expected_fields: dict[str, Any] = Field(default_factory=dict)
    actual_fields: dict[str, Any] = Field(default_factory=dict)
    matched_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    mismatched_fields: list[str] = Field(default_factory=list)
    extra_fields: list[str] = Field(default_factory=list)
    check_passed: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsFeishuReadbackSummary(BaseModel):
    """Summary for controlled Feishu readback smoke."""

    schema_version: str = "1.0"
    summary_type: str = "controlled_feishu_readback_summary"
    job_id: str
    job_type: XhsFeishuJobType
    status: str
    operation: XhsFeishuReadbackOperation
    dry_run: bool = True
    readback_enabled: bool = False
    real_readback_allowed: bool = False
    record_id_present: bool = False
    expected_field_count: int = 0
    actual_field_count: int = 0
    matched_field_count: int = 0
    mismatched_field_count: int = 0
    missing_field_count: int = 0
    extra_field_count: int = 0
    check_passed: bool = False
    request_path: str | None = None
    expected_path: str | None = None
    actual_path: str | None = None
    check_path: str | None = None
    summary_path: str | None = None
    created_at: str
    error_code: str | None = None
    error_message: str | None = None
