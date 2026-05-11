from typing import Any, Literal

from pydantic import BaseModel, Field


YingdaoSelectorMappingJobType = Literal["xhs_search", "xhs_publish"]


class YingdaoSelectorCandidate(BaseModel):
    """One selector candidate for a local HTML sandbox element."""

    selector: str
    selector_type: str
    unique: bool = True


class YingdaoSelectorMappingRuntime(BaseModel):
    """Runtime flags reported by local selector confirmation."""

    tool: str = "yingdao_desktop"
    mode: str = "manual_selector_mapping_confirmation"
    opened_local_html: bool = True
    opened_external_url: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False


class YingdaoMappedElement(BaseModel):
    """Mapped local HTML element for Yingdao desktop guidance."""

    field_key: str
    label: str | None = None
    element_id: str
    element_name: str | None = None
    tag: str
    type: str | None = None
    required: bool = True
    expected_value: Any = None
    recommended_selector: str
    selector_candidates: list[str] = Field(default_factory=list)
    yingdao_action: dict[str, Any] = Field(default_factory=dict)
    unique: bool = True
    safe: bool = True


class YingdaoSelectorMappingInput(BaseModel):
    """Input manifest for a local HTML selector mapping package."""

    schema_version: str = "1.0"
    mapping_type: str = "local_html_sandbox_selector_mapping"
    job_type: YingdaoSelectorMappingJobType
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_html_sandbox"
    created_at: str
    safe_mode: bool = True
    sandbox_manifest_path: str
    html_path: str
    expected_dom_path: str
    forbidden: dict[str, bool] = Field(default_factory=dict)


class YingdaoSelectorMappingResult(BaseModel):
    """Selector mapping result for local HTML sandbox."""

    schema_version: str = "1.0"
    mapping_type: str = "local_html_sandbox_selector_mapping"
    job_type: YingdaoSelectorMappingJobType
    job_id: str
    html_path: str
    status: str = "success"
    element_count: int = 0
    elements: list[YingdaoMappedElement] = Field(default_factory=list)
    forbidden_text_detected: list[str] = Field(default_factory=list)
    forbidden_url_detected: bool = False
    real_publish_action_detected: bool = False


class YingdaoActionSequenceStep(BaseModel):
    """One Yingdao desktop action sequence step."""

    step: int
    field_key: str
    selector: str
    action_type: str
    value: Any = None
    clear_before_fill: bool | None = None
    required: bool = True
    notes: str | None = None


class YingdaoActionSequence(BaseModel):
    """Action sequence for local HTML selector mapping."""

    schema_version: str = "1.0"
    mapping_type: str = "local_html_sandbox_action_sequence"
    job_type: YingdaoSelectorMappingJobType
    job_id: str
    status: str = "success"
    actions: list[YingdaoActionSequenceStep] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)


class YingdaoSelectorMappingConfirmation(BaseModel):
    """Confirmation written by Yingdao desktop or local mock-confirm."""

    schema_version: str = "1.0"
    mapping_type: str = "yingdao_selector_mapping_confirmation"
    job_type: YingdaoSelectorMappingJobType
    job_id: str
    status: str = "success"
    confirmed_at: str
    runtime: YingdaoSelectorMappingRuntime = Field(default_factory=YingdaoSelectorMappingRuntime)
    confirmed_selectors: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    notes: str | None = None


class YingdaoSelectorMappingPrepareRequest(BaseModel):
    """Prepare request for selector mapping."""

    job_id: str
    account_id: str
    job_type: Literal["search", "publish"] = "search"
    keyword: str | None = None
    limit: int = 20
    title: str | None = None
    body: str | None = None
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class YingdaoSelectorMappingPrepareResult(BaseModel):
    """Result returned after writing selector mapping files."""

    job_id: str
    job_type: YingdaoSelectorMappingJobType
    status: str
    mapping_dir: str
    selector_mapping_input_path: str
    selector_mapping_path: str
    action_sequence_path: str
    mapping_report_path: str
    confirmation_path: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class YingdaoSelectorMappingSummary(BaseModel):
    """Verification summary for selector mapping confirmation."""

    confirmation_exists: bool = False
    confirmation_valid: bool = False
    element_count: int = 0
    confirmed_selector_count: int = 0
    missing_selectors: list[str] = Field(default_factory=list)
    selector_empty: bool = False
    opened_external_url: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False
    real_action_executed: bool = False
    forbidden_actions_detected: list[str] = Field(default_factory=list)


class YingdaoSelectorMappingVerifyResult(BaseModel):
    """Verification result for selector mapping confirmation."""

    job_id: str
    job_type: YingdaoSelectorMappingJobType
    status: str
    mapping_dir: str
    confirmation_path: str
    selector_mapping_summary_path: str
    summary: YingdaoSelectorMappingSummary = Field(default_factory=YingdaoSelectorMappingSummary)
    confirmation: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
