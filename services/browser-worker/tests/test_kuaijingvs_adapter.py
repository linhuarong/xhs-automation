import pytest

from app.integrations.kuaijingvs_adapter import KuaJingVSAdapter
from app.utils.errors import (
    XHS_EXTERNAL_LIVE_CHECK_DISABLED,
    XHS_KJVS_DISCOVERY_FAILED,
    XHS_KJVS_RESPONSE_INVALID,
    WorkerError,
)


class FakeHttpClient:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def get_json(self, url, headers=None):
        self.calls.append((url, headers))
        if self.exc:
            raise self.exc
        return self.response


def test_adapter_blocks_when_live_readonly_disabled() -> None:
    client = FakeHttpClient({"shops": []})
    adapter = KuaJingVSAdapter(
        api_base_url="http://127.0.0.1:49709",
        http_client=client,
        env={"XHS_ALLOW_LIVE_READONLY_CHECKS": "false"},
    )

    with pytest.raises(WorkerError) as exc:
        adapter.list_shops_readonly()

    assert exc.value.error_code == XHS_EXTERNAL_LIVE_CHECK_DISABLED
    assert client.calls == []


def test_adapter_list_shops_readonly_uses_mock_http() -> None:
    client = FakeHttpClient(
        {
            "shops": [
                {
                    "shop_id": "123",
                    "shop_name": "测试店铺",
                    "token": "secret-token",
                    "name": "ignored",
                }
            ]
        }
    )
    adapter = KuaJingVSAdapter(
        api_base_url="http://127.0.0.1:49709/v1",
        api_id="id",
        api_secret="secret",
        http_client=client,
        env={"XHS_ALLOW_LIVE_READONLY_CHECKS": "true"},
    )

    shops = adapter.list_shops_readonly()

    assert client.calls[0][0] == "http://127.0.0.1:49709/v1/shops?page=1&size=50"
    assert client.calls[0][1] == {"x-app-id": "id", "x-app-secret": "secret"}
    assert shops == [{"shop_id": "123", "shop_name": "测试店铺", "raw_keys": ["name", "shop_id", "shop_name"]}]


def test_adapter_parses_data_list_response() -> None:
    adapter = KuaJingVSAdapter(
        api_base_url="http://127.0.0.1:49709",
        http_client=FakeHttpClient({"data": [{"id": 1, "name": "店铺"}]}),
        env={"XHS_ALLOW_LIVE_READONLY_CHECKS": "true"},
    )

    assert adapter.list_shops_readonly()[0]["shop_id"] == "1"


def test_adapter_non_json_shape_returns_invalid() -> None:
    adapter = KuaJingVSAdapter(
        api_base_url="http://127.0.0.1:49709",
        http_client=FakeHttpClient("not-json-object"),
        env={"XHS_ALLOW_LIVE_READONLY_CHECKS": "true"},
    )

    with pytest.raises(WorkerError) as exc:
        adapter.list_shops_readonly()

    assert exc.value.error_code == XHS_KJVS_RESPONSE_INVALID


def test_adapter_timeout_returns_discovery_failed() -> None:
    adapter = KuaJingVSAdapter(
        api_base_url="http://127.0.0.1:49709",
        http_client=FakeHttpClient(exc=TimeoutError("timed out")),
        env={"XHS_ALLOW_LIVE_READONLY_CHECKS": "true"},
    )

    with pytest.raises(WorkerError) as exc:
        adapter.list_shops_readonly()

    assert exc.value.error_code == XHS_KJVS_DISCOVERY_FAILED


def test_discover_shops_readonly_returns_stable_structure() -> None:
    adapter = KuaJingVSAdapter(
        api_base_url="http://127.0.0.1:49709",
        http_client=FakeHttpClient({"shops": [{"shopId": "123", "shopName": "店铺"}]}),
        env={"XHS_ALLOW_LIVE_READONLY_CHECKS": "true"},
    )

    result = adapter.discover_shops_readonly()

    assert result["status"] == "success"
    assert result["shop_count"] == 1
