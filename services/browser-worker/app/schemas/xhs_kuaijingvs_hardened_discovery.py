from typing import Any

from pydantic import BaseModel, Field


class KuaJingVSSanitizationResult(BaseModel):
    """Sanitization metadata for hardened discovery evidence."""

    enabled: bool = True
    sensitive_keys_removed: list[str] = Field(default_factory=list)
    sensitive_value_scan_passed: bool = True


class KuaJingVSHardenedShop(BaseModel):
    """Safe KuaJingVS shop projection for account binding."""

    shop_id: str
    shop_name: str
    normalized_shop_name: str
    provider_type: str = "kuaijingvs_yingdao_rpa"
    raw_keys: list[str] = Field(default_factory=list)
    safe: bool = True
    warnings: list[str] = Field(default_factory=list)


class KuaJingVSHardenedDiscoveryEvidence(BaseModel):
    """Hardened readonly discovery evidence."""

    schema_version: str = "1.0"
    evidence_type: str = "kuaijingvs_readonly_discovery_hardened"
    status: str
    source_evidence_path: str
    generated_at: str
    safe_mode: bool = True
    sanitization: KuaJingVSSanitizationResult = Field(default_factory=KuaJingVSSanitizationResult)
    shop_count: int = 0
    shops: list[KuaJingVSHardenedShop] = Field(default_factory=list)
    evidence_hash: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    forbidden: dict[str, bool] = Field(default_factory=dict)


class KuaJingVSHardenedDiscoverySummary(BaseModel):
    """Summary for hardened discovery evidence."""

    schema_version: str = "1.0"
    summary_type: str = "kuaijingvs_readonly_discovery_hardened_summary"
    status: str
    generated_at: str
    source_evidence_path: str
    hardened_evidence_path: str
    shop_count: int = 0
    safe_shop_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    sensitive_key_removed_count: int = 0
    sensitive_value_scan_passed: bool = True
    evidence_hash: str | None = None
    ready_for_strict_account_binding: bool = False


class KuaJingVSDiscoveryHardenRequest(BaseModel):
    """API request for hardening local discovery evidence."""

    source_evidence_path: str | None = None


class KuaJingVSDiscoveryHardenResult(BaseModel):
    """API result for discovery hardening."""

    status: str
    hardened_evidence_path: str | None = None
    summary_path: str | None = None
    audit_path: str | None = None
    shop_count: int = 0
    sensitive_value_scan_passed: bool = False
    evidence_hash: str | None = None
    summary: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
