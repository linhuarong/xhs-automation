from typing import Any, Literal

from pydantic import BaseModel, Field


XhsAccountBindingJobType = Literal["xhs_search", "xhs_publish"]


class XhsMappedProfile(BaseModel):
    """Account profile from local KuaJingVS profile map."""

    account_id: str
    shop_id: str | None = None
    shop_name: str | None = None
    provider_type: str = "kuaijingvs_yingdao_rpa"


class XhsDiscoveryMatchedShop(BaseModel):
    """Sanitized shop matched from KuaJingVS discovery evidence."""

    shop_id: str | None = None
    shop_name: str | None = None
    name_matches_profile_map: bool = False


class XhsAccountBindingInput(BaseModel):
    """Input contract for account binding checks."""

    schema_version: str = "1.0"
    binding_type: str = "kuaijingvs_profile_to_yingdao_local_form_fill"
    job_type: XhsAccountBindingJobType
    job_id: str
    account_id: str
    provider_type: str = "kuaijingvs_yingdao_rpa"
    created_at: str
    safe_mode: bool = True
    profile_map_path: str
    kuaijingvs_discovery_evidence_path: str
    actual_form_fill_input_path: str
    forbidden: dict[str, bool] = Field(default_factory=dict)


class XhsAccountBindingContext(BaseModel):
    """Resolved account binding context."""

    schema_version: str = "1.0"
    binding_type: str = "kuaijingvs_profile_to_yingdao_local_form_fill"
    job_type: XhsAccountBindingJobType
    job_id: str
    account_id: str
    status: str
    profile_map: dict[str, Any] = Field(default_factory=dict)
    mapped_profile: XhsMappedProfile | None = None
    discovery: dict[str, Any] = Field(default_factory=dict)
    matched_shop: XhsDiscoveryMatchedShop | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    safe_mode: bool = True
    real_actions: dict[str, bool] = Field(default_factory=dict)


class XhsAccountBindingConfirmationRuntime(BaseModel):
    """Runtime flags in account binding confirmation."""

    tool: str = "yingdao_desktop"
    mode: str = "local_account_binding_confirmation"
    opened_shop: bool = False
    closed_shop: bool = False
    opened_xhs: bool = False
    opened_external_url: bool = False
    called_yingdao_openapi: bool = False
    called_kuaijingvs_open_shop: bool = False
    real_search_executed: bool = False
    real_publish_executed: bool = False


class XhsAccountBindingConfirmation(BaseModel):
    """Confirmation written by Yingdao desktop or local mock-confirm."""

    schema_version: str = "1.0"
    binding_type: str = "kuaijingvs_profile_to_yingdao_local_form_fill_confirmation"
    job_type: XhsAccountBindingJobType
    job_id: str
    account_id: str
    status: str = "success"
    confirmed_at: str
    confirmed_profile: XhsMappedProfile
    runtime: XhsAccountBindingConfirmationRuntime = Field(default_factory=XhsAccountBindingConfirmationRuntime)
    notes: str | None = None


class XhsAccountBindingPrepareRequest(BaseModel):
    """Prepare request for account binding."""

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


class XhsAccountBindingPrepareResult(BaseModel):
    """Result returned after writing account binding package."""

    job_id: str
    job_type: XhsAccountBindingJobType
    status: str
    binding_status: str
    account_binding_dir: str
    account_binding_input_path: str
    account_binding_context_path: str
    actual_form_fill_input_path: str
    confirmation_path: str
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsAccountBindingSummary(BaseModel):
    """Verification summary for account binding confirmation."""

    confirmation_exists: bool = False
    confirmation_valid: bool = False
    binding_status: str | None = None
    account_id: str | None = None
    shop_id: str | None = None
    opened_shop: bool = False
    closed_shop: bool = False
    opened_xhs: bool = False
    opened_external_url: bool = False
    called_yingdao_openapi: bool = False
    called_kuaijingvs_open_shop: bool = False
    real_action_executed: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class XhsAccountBindingVerifyResult(BaseModel):
    """Verification result for account binding confirmation."""

    job_id: str
    job_type: XhsAccountBindingJobType
    status: str
    account_binding_dir: str
    confirmation_path: str
    account_binding_summary_path: str
    summary: XhsAccountBindingSummary = Field(default_factory=XhsAccountBindingSummary)
    confirmation: dict[str, Any] | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsAccountBindingStrictRules(BaseModel):
    """Strict account binding rules."""

    require_profile_map: bool = True
    require_account_id: bool = True
    require_hardened_discovery: bool = True
    require_shop_id_match: bool = True
    require_shop_name_match: bool = True
    require_provider_type_allowed: bool = True
    fail_on_sensitive_field: bool = True
    fail_on_name_mismatch: bool = True


class XhsAccountBindingStrictInput(BaseModel):
    """Input contract for strict account binding checks."""

    schema_version: str = "1.0"
    strict_check_type: str = "xhs_account_binding_strict_mode"
    job_type: XhsAccountBindingJobType
    job_id: str
    account_id: str
    provider_type: str = "kuaijingvs_yingdao_rpa"
    created_at: str
    safe_mode: bool = True
    profile_map_path: str
    hardened_discovery_path: str
    account_binding_context_path: str | None = None
    strict_rules: XhsAccountBindingStrictRules = Field(default_factory=XhsAccountBindingStrictRules)
    forbidden: dict[str, bool] = Field(default_factory=dict)


class XhsAccountBindingStrictResult(BaseModel):
    """Result for strict account binding checks."""

    schema_version: str = "1.0"
    strict_check_type: str = "xhs_account_binding_strict_mode_result"
    job_type: XhsAccountBindingJobType
    job_id: str
    account_id: str
    status: str
    binding_status: str
    checked_at: str
    checks: dict[str, bool] = Field(default_factory=dict)
    matched_profile: XhsMappedProfile | None = None
    matched_shop: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    real_actions: dict[str, bool] = Field(default_factory=dict)
    strict_binding_dir: str | None = None
    strict_binding_input_path: str | None = None
    strict_binding_result_path: str | None = None
    strict_binding_summary_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class XhsAccountBindingStrictSummary(BaseModel):
    """Summary for strict account binding checks."""

    schema_version: str = "1.0"
    summary_type: str = "xhs_account_binding_strict_mode_summary"
    status: str
    binding_status: str
    job_type: XhsAccountBindingJobType
    job_id: str
    account_id: str
    strict_binding_result_path: str
    profile_map_exists: bool = False
    hardened_discovery_exists: bool = False
    shop_id_matched: bool = False
    shop_name_matched: bool = False
    provider_type_allowed: bool = False
    error_code: str | None = None
    error_message: str | None = None
