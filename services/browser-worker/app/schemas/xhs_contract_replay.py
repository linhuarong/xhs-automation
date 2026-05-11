from typing import Any, Literal

from pydantic import BaseModel, Field


XhsContractReplayJobType = Literal["xhs_search", "xhs_publish"]
XhsContractReplayTarget = Literal[
    "n8n_mock_search_webhook",
    "n8n_mock_publish_webhook",
    "openclaw_mock_job_status",
]
XhsContractReplayType = Literal[
    "local_n8n_contract_replay",
    "local_openclaw_contract_replay",
    "local_contract_replay_result",
]


class XhsContractReplayForbiddenActions(BaseModel):
    """Forbidden real actions for local-only contract replay."""

    external_n8n_call: bool = True
    external_openclaw_call: bool = True
    open_shop: bool = True
    open_xhs: bool = True
    real_search: bool = True
    real_publish: bool = True
    click_final_publish: bool = True
    yingdao_openapi: bool = True


class XhsN8nReplayPayload(BaseModel):
    """Local replay payload for n8n mock webhook contracts."""

    schema_version: str = "1.0"
    replay_type: Literal["local_n8n_contract_replay"] = "local_n8n_contract_replay"
    target: Literal["n8n_mock_search_webhook", "n8n_mock_publish_webhook"]
    job_type: XhsContractReplayJobType
    job_id: str
    account_id: str
    provider_type: str = "kuaijingvs_yingdao_rpa"
    created_at: str
    safe_mode: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    strict_account_binding: dict[str, Any] = Field(default_factory=dict)
    hardened_discovery: dict[str, Any] = Field(default_factory=dict)
    forbidden: XhsContractReplayForbiddenActions = Field(default_factory=XhsContractReplayForbiddenActions)


class XhsOpenClawReplayPayload(BaseModel):
    """Local replay payload for OpenClaw mock job-status contract."""

    schema_version: str = "1.0"
    replay_type: Literal["local_openclaw_contract_replay"] = "local_openclaw_contract_replay"
    target: Literal["openclaw_mock_job_status"] = "openclaw_mock_job_status"
    job_type: XhsContractReplayJobType
    job_id: str
    account_id: str
    created_at: str
    safe_mode: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_status_context: dict[str, Any] = Field(default_factory=dict)
    forbidden: XhsContractReplayForbiddenActions = Field(default_factory=XhsContractReplayForbiddenActions)


class XhsContractReplayResult(BaseModel):
    """Result written after local mock-route replay."""

    schema_version: str = "1.0"
    replay_type: Literal["local_contract_replay_result"] = "local_contract_replay_result"
    target: XhsContractReplayTarget
    job_type: XhsContractReplayJobType
    job_id: str
    status: str
    replayed_at: str
    local_route: str
    http_status_code: int
    response_status: str
    strict_binding_included: bool = False
    strict_binding_status: str | None = None
    hardened_discovery_included: bool = False
    sensitive_scan_passed: bool = False
    real_actions: dict[str, bool] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class XhsContractReplaySummary(BaseModel):
    """Summary written for local contract replay."""

    schema_version: str = "1.0"
    summary_type: str = "local_contract_replay_summary"
    target: XhsContractReplayTarget
    job_type: XhsContractReplayJobType
    job_id: str
    status: str
    payload_path: str
    result_path: str
    strict_binding_status: str | None = None
    sensitive_scan_passed: bool = False
    external_calls_made: bool = False
    ready_for_real_n8n_workflow_design: bool = False
    ready_for_openclaw_status_design: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsContractReplayPrepareRequest(BaseModel):
    """Generic local contract replay request."""

    job_id: str
    account_id: str
    job_type: Literal["search", "publish", "xhs_search", "xhs_publish"] = "search"
    keyword: str | None = None
    limit: int = 20
    title: str | None = None
    body: str | None = None
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class XhsContractReplayPrepareResult(BaseModel):
    """API/service result for one local replay target."""

    job_id: str
    job_type: XhsContractReplayJobType
    target: XhsContractReplayTarget
    status: str
    replay_dir: str
    replay_payload_path: str
    replay_result_path: str
    replay_summary_path: str
    local_route: str | None = None
    strict_binding_status: str | None = None
    sensitive_scan_passed: bool = False
    external_calls_made: bool = False
    result: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsContractReplayAllResult(BaseModel):
    """Result for all local replays for one job."""

    job_id: str
    job_type: XhsContractReplayJobType
    status: str
    strict_binding_status: str | None = None
    n8n_replay: dict[str, Any] | None = None
    openclaw_replay: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
