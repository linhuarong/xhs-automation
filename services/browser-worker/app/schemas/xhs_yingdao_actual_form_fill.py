from typing import Any, Literal

from pydantic import BaseModel, Field


YingdaoActualFormFillJobType = Literal["xhs_search", "xhs_publish"]


class YingdaoActualFormFillRuntime(BaseModel):
    """Runtime flags reported by actual local HTML form-fill smoke runs."""

    tool: str = "yingdao_desktop"
    mode: str = "actual_local_html_form_fill"
    opened_local_html: bool = True
    opened_external_url: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False


class YingdaoActualFormFillInput(BaseModel):
    """Input contract for the local actual form-fill smoke package."""

    schema_version: str = "1.0"
    smoke_type: str = "yingdao_desktop_actual_local_form_fill"
    job_type: YingdaoActualFormFillJobType
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_html_sandbox"
    created_at: str
    safe_mode: bool = True
    html_path: str
    html_uri: str
    selector_mapping_path: str
    action_sequence_path: str
    expected_trace_path: str
    expected_result_path: str
    allowed_target: dict[str, Any] = Field(default_factory=dict)
    forbidden: dict[str, bool] = Field(default_factory=dict)
    account_binding: dict[str, Any] | None = None


class YingdaoActualFormFillRunbookStep(BaseModel):
    """One step for a desktop local HTML form-fill runbook."""

    step: int
    action: str
    selector: str | None = None
    field_key: str | None = None
    target: str | None = None
    value: Any = None
    clear_before_fill: bool | None = None
    safety: str | None = None
    required: bool = False


class YingdaoActualFormFillRunbook(BaseModel):
    """Runbook JSON consumed by a manual Yingdao desktop local smoke flow."""

    schema_version: str = "1.0"
    smoke_type: str = "yingdao_desktop_actual_local_form_fill_runbook"
    job_type: YingdaoActualFormFillJobType
    job_id: str
    steps: list[YingdaoActualFormFillRunbookStep] = Field(default_factory=list)
    forbidden_steps: list[str] = Field(default_factory=list)


class YingdaoActualFilledField(BaseModel):
    """One filled local sandbox field."""

    step: int
    field_key: str
    selector: str
    value: Any = None
    success: bool = True


class YingdaoActualButtonAction(BaseModel):
    """One local sandbox button action."""

    step: int
    element_id: str
    selector: str
    action: str = "click"
    success: bool = True
    local_simulate_button: bool = True


class YingdaoActualFormFillTrace(BaseModel):
    """Trace written by Yingdao desktop or local mock-write."""

    schema_version: str = "1.0"
    smoke_type: str = "yingdao_desktop_actual_local_form_fill"
    job_type: YingdaoActualFormFillJobType
    job_id: str
    status: str
    filled_at: str
    runtime: YingdaoActualFormFillRuntime = Field(default_factory=YingdaoActualFormFillRuntime)
    target: dict[str, Any] = Field(default_factory=dict)
    filled_fields: list[YingdaoActualFilledField] = Field(default_factory=list)
    button_actions: list[YingdaoActualButtonAction] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)


class YingdaoActualFormFillResult(BaseModel):
    """Validation result written by Yingdao desktop or local mock-write."""

    schema_version: str = "1.0"
    smoke_type: str = "yingdao_desktop_actual_local_form_fill"
    job_type: YingdaoActualFormFillJobType
    job_id: str
    status: str
    validated_at: str
    required_field_count: int = 0
    filled_required_field_count: int = 0
    missing_required_fields: list[str] = Field(default_factory=list)
    value_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)


class YingdaoActualFormFillPrepareRequest(BaseModel):
    """Prepare request for actual local form-fill smoke."""

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


class YingdaoActualFormFillPrepareResult(BaseModel):
    """Result returned after writing actual local form-fill smoke files."""

    job_id: str
    job_type: YingdaoActualFormFillJobType
    status: str
    actual_form_fill_dir: str
    html_path: str
    html_uri: str
    actual_form_fill_input_path: str
    actual_form_fill_runbook_path: str
    expected_trace_path: str
    expected_result_path: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class YingdaoActualFormFillSummary(BaseModel):
    """Verification summary for actual local form-fill smoke."""

    trace_exists: bool = False
    result_exists: bool = False
    trace_valid: bool = False
    result_valid: bool = False
    opened_local_html: bool = False
    opened_external_url: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False
    real_action_executed: bool = False
    missing_required_fields: list[str] = Field(default_factory=list)
    value_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)


class YingdaoActualFormFillVerifyResult(BaseModel):
    """Verification result for actual local form-fill smoke."""

    job_id: str
    job_type: YingdaoActualFormFillJobType
    status: str
    actual_form_fill_dir: str
    trace_path: str
    result_path: str
    actual_form_fill_summary_path: str
    summary: YingdaoActualFormFillSummary = Field(default_factory=YingdaoActualFormFillSummary)
    trace: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
