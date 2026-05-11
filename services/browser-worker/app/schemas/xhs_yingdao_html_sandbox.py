from typing import Any, Literal

from pydantic import BaseModel, Field


YingdaoHtmlSandboxJobType = Literal["xhs_search", "xhs_publish"]


class YingdaoHtmlSandboxRuntime(BaseModel):
    """Runtime flags reported by local HTML sandbox runs."""

    tool: str = "yingdao_desktop"
    mode: str = "manual_local_html_sandbox"
    opened_local_html: bool = True
    opened_external_url: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False


class YingdaoHtmlSandboxManifest(BaseModel):
    """Manifest for a generated local static HTML sandbox."""

    schema_version: str = "1.0"
    sandbox_type: str = "local_static_html"
    job_type: YingdaoHtmlSandboxJobType
    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_html_sandbox"
    created_at: str
    safe_mode: bool = True
    html_path: str
    html_uri: str
    expected_dom_path: str
    expected_trace_path: str
    expected_result_path: str
    forbidden: dict[str, bool] = Field(default_factory=dict)


class YingdaoHtmlExpectedDomElement(BaseModel):
    """One expected local sandbox DOM element."""

    id: str
    type: str
    expected_value: str | None = None
    expected_value_contains: str | None = None
    expected_checked: bool | None = None


class YingdaoHtmlExpectedDom(BaseModel):
    """Expected DOM contract for local static HTML sandbox."""

    schema_version: str = "1.0"
    sandbox_type: str = "local_static_html"
    job_type: YingdaoHtmlSandboxJobType
    job_id: str
    required_elements: list[YingdaoHtmlExpectedDomElement] = Field(default_factory=list)
    forbidden_text: list[str] = Field(default_factory=list)


class YingdaoHtmlSandboxTrace(BaseModel):
    """Trace written by Yingdao desktop or local mock-write."""

    schema_version: str = "1.0"
    sandbox_type: str = "local_static_html"
    job_type: YingdaoHtmlSandboxJobType
    job_id: str
    status: str
    filled_at: str
    runtime: YingdaoHtmlSandboxRuntime = Field(default_factory=YingdaoHtmlSandboxRuntime)
    filled_fields: list[dict[str, Any]] = Field(default_factory=list)
    button_actions: list[dict[str, Any]] = Field(default_factory=list)


class YingdaoHtmlSandboxResult(BaseModel):
    """Result written by Yingdao desktop or local mock-write."""

    schema_version: str = "1.0"
    sandbox_type: str = "local_static_html"
    job_type: YingdaoHtmlSandboxJobType
    job_id: str
    status: str
    validated_at: str
    required_element_count: int = 0
    filled_element_count: int = 0
    missing_required_elements: list[str] = Field(default_factory=list)
    value_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    forbidden_text_detected: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)


class YingdaoHtmlSandboxPrepareRequest(BaseModel):
    """Prepare request for local static HTML sandbox."""

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


class YingdaoHtmlSandboxPrepareResult(BaseModel):
    """Result returned after writing local static HTML sandbox files."""

    job_id: str
    job_type: YingdaoHtmlSandboxJobType
    status: str
    sandbox_dir: str
    html_path: str
    html_uri: str
    manifest_path: str
    expected_dom_path: str
    expected_trace_path: str
    expected_result_path: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class YingdaoHtmlSandboxSummary(BaseModel):
    """Verification summary for local static HTML sandbox."""

    trace_exists: bool = False
    result_exists: bool = False
    trace_valid: bool = False
    result_valid: bool = False
    opened_external_url: bool = False
    opened_xhs: bool = False
    called_external_api: bool = False
    clicked_real_publish: bool = False
    real_action_executed: bool = False
    missing_required_elements: list[str] = Field(default_factory=list)
    value_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    forbidden_text_detected: list[str] = Field(default_factory=list)


class YingdaoHtmlSandboxVerifyResult(BaseModel):
    """Verification result for local static HTML sandbox."""

    job_id: str
    job_type: YingdaoHtmlSandboxJobType
    status: str
    sandbox_dir: str
    trace_path: str
    result_path: str
    sandbox_summary_path: str
    summary: YingdaoHtmlSandboxSummary = Field(default_factory=YingdaoHtmlSandboxSummary)
    trace: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
