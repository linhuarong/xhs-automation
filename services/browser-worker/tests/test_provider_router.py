import pytest

from app.providers import (
    KuaJingVSLocalFileTriggerProvider,
    KuaJingVSYingdaoRpaProvider,
    ReservedProvider,
    SeleniumChromeProvider,
    UnsupportedProviderError,
    YingdaoRpaProvider,
    get_provider,
)


def test_get_provider_yingdao_rpa_returns_yingdao_provider() -> None:
    provider = get_provider("yingdao_rpa")

    assert isinstance(provider, YingdaoRpaProvider)


def test_get_provider_selenium_chrome_returns_debug_provider() -> None:
    provider = get_provider("selenium_chrome")

    assert isinstance(provider, SeleniumChromeProvider)


def test_get_provider_kuaijingvs_yingdao_rpa_returns_composed_provider() -> None:
    provider = get_provider("kuaijingvs_yingdao_rpa")

    assert isinstance(provider, KuaJingVSYingdaoRpaProvider)


def test_get_provider_kuaijingvs_local_file_trigger_returns_file_provider() -> None:
    provider = get_provider("kuaijingvs_local_file_trigger")

    assert isinstance(provider, KuaJingVSLocalFileTriggerProvider)


def test_get_provider_manual_returns_reserved_provider() -> None:
    provider = get_provider("manual")

    assert isinstance(provider, ReservedProvider)


def test_get_provider_unknown_raises_clear_error() -> None:
    with pytest.raises(UnsupportedProviderError, match="unknown_provider"):
        get_provider("unknown_provider")
