from pydantic import BaseModel, Field


class KuaJingVSShop(BaseModel):
    """Sanitized KuaJingVS shop discovery record."""

    shop_id: str | None = None
    shop_name: str | None = None
    raw_keys: list[str] = Field(default_factory=list)


class KuaJingVSMatchedAccount(BaseModel):
    """Profile map account matched against discovered shops."""

    account_id: str
    shop_id: str | None = None
    shop_name: str | None = None
    matched: bool = False
    warning: str | None = None


class KuaJingVSDiscoveryResult(BaseModel):
    """KuaJingVS live-readonly discovery result."""

    status: str
    mode: str = "live_readonly"
    safe_mode: bool = True
    api_base_url_configured: bool = False
    live_readonly_enabled: bool = False
    shop_count: int = 0
    shops: list[KuaJingVSShop] = Field(default_factory=list)
    profile_map_path: str | None = None
    profile_map_exists: bool = False
    profile_map_valid: bool = False
    matched_accounts: list[KuaJingVSMatchedAccount] = Field(default_factory=list)
    unmatched_accounts: list[KuaJingVSMatchedAccount] = Field(default_factory=list)
    unmapped_shops: list[KuaJingVSShop] = Field(default_factory=list)
    matched_account_count: int = 0
    unmatched_account_count: int = 0
    evidence_json_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
