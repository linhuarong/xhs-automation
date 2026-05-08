from app.providers.base import (
    BrowserProvider,
    BrowserSession,
    ReservedProvider,
    UnsupportedProviderError,
)
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
        # Task 24A does not implement KuaJingVS OpenAPI yet. For smoke tests,
        # assume the browser environment has already been opened externally and
        # let Yingdao read/write evidence through the RPA application.
        return YingdaoRpaProvider()
    if normalized_provider_type == "manual":
        return ReservedProvider(
            provider_type="manual",
            message="provider_type manual is reserved but not implemented.",
        )
    raise UnsupportedProviderError(f"Unsupported provider_type: {provider_type}")


__all__ = [
    "BrowserProvider",
    "BrowserSession",
    "ReservedProvider",
    "UnsupportedProviderError",
    "SeleniumChromeProvider",
    "YingdaoRpaProvider",
    "get_provider",
]
