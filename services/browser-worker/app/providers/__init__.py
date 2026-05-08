from app.providers.base import (
    BrowserProvider,
    BrowserSession,
    ReservedProvider,
    UnsupportedProviderError,
)
from app.providers.kuaijingvs_local_file_trigger import KuaJingVSLocalFileTriggerProvider
from app.providers.kuaijingvs_yingdao_rpa import KuaJingVSYingdaoRpaProvider
from app.providers.selenium_chrome import SeleniumChromeProvider
from app.providers.yingdao_rpa import YingdaoRpaProvider


def get_provider(provider_type: str) -> BrowserProvider:
    """Return a provider by provider_type."""
    normalized_provider_type = (provider_type or "").strip()
    if normalized_provider_type == "selenium_chrome":
        return SeleniumChromeProvider()
    if normalized_provider_type == "yingdao_rpa":
        return YingdaoRpaProvider()
    if normalized_provider_type == "kuaijingvs_yingdao_rpa":
        return KuaJingVSYingdaoRpaProvider()
    if normalized_provider_type == "kuaijingvs_local_file_trigger":
        return KuaJingVSLocalFileTriggerProvider()
    if normalized_provider_type == "manual":
        return ReservedProvider(
            provider_type="manual",
            message="provider_type manual is reserved but not implemented.",
        )
    raise UnsupportedProviderError(f"Unsupported provider_type: {provider_type}")


__all__ = [
    "BrowserProvider",
    "BrowserSession",
    "KuaJingVSLocalFileTriggerProvider",
    "ReservedProvider",
    "UnsupportedProviderError",
    "KuaJingVSYingdaoRpaProvider",
    "SeleniumChromeProvider",
    "YingdaoRpaProvider",
    "get_provider",
]
