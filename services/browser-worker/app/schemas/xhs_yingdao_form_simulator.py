from typing import Any, Literal

from pydantic import BaseModel, Field


YingdaoFormSimulatorJobType = Literal["xhs_search", "xhs_publish"]


class YingdaoFormSimulatorRuntime(BaseModel):
    """Runtime safety flags for browserless form-fill simulation."""

    tool: str = "yingdao_desktop"
    mode: str = "manual_browserless_simulator"
    opened_browser: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False


class YingdaoFormFieldSpec(BaseModel):
    """One fake form field definition."""

    field_key: str
    label: str
    type: str
    required: bool = False
    source_path: str


class YingdaoFormAction(BaseModel):
    """One expected or traced browserless form action."""

    step: int
    action: str
    field_key: str
    value: Any = None
    success: bool | None = None


class YingdaoFormSimulatorInput(BaseModel):
    """Input package for a browserless form-fill simulator run."""

    schema_version: str = "1.0"
    simulator_type: str = "browserless_form_fill"
    job_type: YingdaoFormSimulatorJobType
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_file_trigger"
    created_at: str
    safe_mode: bool = True
    source_active_job_path: str
    form_spec_path: str
    expected_actions_path: str
    expected_trace_path: str
    expected_result_path: str
    payload: dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)


class YingdaoFormSpec(BaseModel):
    """Fake form field specification."""

    schema_version: str = "1.0"
    job_type: YingdaoFormSimulatorJobType
    form_name: str
    fields: list[YingdaoFormFieldSpec] = Field(default_factory=list)


class YingdaoExpectedActions(BaseModel):
    """Expected browserless form-fill action sequence."""

    schema_version: str = "1.0"
    job_type: YingdaoFormSimulatorJobType
    job_id: str
    actions: list[YingdaoFormAction] = Field(default_factory=list)
    forbidden_final_action: str | None = None


class YingdaoFormFillTrace(BaseModel):
    """Trace written by Yingdao desktop or mock-write."""

    schema_version: str = "1.0"
    simulator_type: str = "browserless_form_fill"
    job_type: YingdaoFormSimulatorJobType
    job_id: str
    status: str
    filled_at: str
    runtime: YingdaoFormSimulatorRuntime = Field(default_factory=YingdaoFormSimulatorRuntime)
    actions: list[YingdaoFormAction] = Field(default_factory=list)


class YingdaoFormSimulatorResult(BaseModel):
    """Result written by Yingdao desktop or mock-write."""

    schema_version: str = "1.0"
    simulator_type: str = "browserless_form_fill"
    job_type: YingdaoFormSimulatorJobType
    job_id: str
    status: str
    validated_at: str
    field_count: int = 0
    filled_field_count: int = 0
    missing_required_fields: list[str] = Field(default_factory=list)
    unexpected_actions: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)


class YingdaoFormSimulatorPrepareRequest(BaseModel):
    """Prepare request for browserless form-fill simulator."""

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


class YingdaoFormSimulatorPrepareResult(BaseModel):
    """Result returned after writing a simulator package."""

    job_id: str
    job_type: YingdaoFormSimulatorJobType
    status: str
    simulator_dir: str
    simulator_input_path: str
    form_spec_path: str
    expected_actions_path: str
    expected_trace_path: str
    expected_result_path: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class YingdaoFormSimulatorSummary(BaseModel):
    """Verification summary for browserless form-fill simulator."""

    trace_exists: bool = False
    result_exists: bool = False
    trace_valid: bool = False
    result_valid: bool = False
    opened_browser: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False
    real_action_executed: bool = False
    missing_required_fields: list[str] = Field(default_factory=list)
    unexpected_actions: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)


class YingdaoFormSimulatorVerifyResult(BaseModel):
    """Verification result for browserless form-fill simulator."""

    job_id: str
    job_type: YingdaoFormSimulatorJobType
    status: str
    simulator_dir: str
    trace_path: str
    result_path: str
    simulator_summary_path: str
    summary: YingdaoFormSimulatorSummary = Field(default_factory=YingdaoFormSimulatorSummary)
    trace: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
