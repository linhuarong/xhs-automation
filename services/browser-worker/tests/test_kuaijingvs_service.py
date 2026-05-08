import json

import pytest

from app.services.kuaijingvs_service import KuaJingVSService
from app.utils.errors import (
    KJVS_CONFIG_ERROR,
    KJVS_ENV_FAILED,
    KJVS_ENV_TIMEOUT,
    KJVS_PROFILE_NOT_FOUND,
    WorkerError,
)


class FakeHttpClient:
    def __init__(self) -> None:
        self.get_responses: list[dict] = []
        self.post_responses: list[dict] = []
        self.gets: list[tuple[str, dict | None]] = []
        self.posts: list[tuple[str, dict, dict | None]] = []

    def get_json(self, url: str, headers: dict | None = None) -> dict:
        self.gets.append((url, headers))
        return self.get_responses.pop(0)

    def post_json(self, url: str, payload: dict, headers: dict | None = None) -> dict:
        self.posts.append((url, payload, headers))
        return self.post_responses.pop(0)


def _profile_map(tmp_path) -> str:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "xhs_dev_01": {
                    "shop_id": "123456",
                    "shop_name": "\u5c0f\u7ea2\u4e66\u6d4b\u8bd5\u8d26\u53f701",
                    "provider_type": "kuaijingvs_yingdao_rpa",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(path)


def test_default_api_base_url() -> None:
    service = KuaJingVSService(http_client=FakeHttpClient())

    assert service.api_base_url == "http://127.0.0.1:49709"


def test_resolve_shop_id_from_profile_map(tmp_path) -> None:
    service = KuaJingVSService(
        profile_map_path=_profile_map(tmp_path),
        http_client=FakeHttpClient(),
    )

    assert service.resolve_shop_id("xhs_dev_01") == "123456"


def test_resolve_shop_id_missing_account_raises(tmp_path) -> None:
    service = KuaJingVSService(
        profile_map_path=_profile_map(tmp_path),
        http_client=FakeHttpClient(),
    )

    with pytest.raises(WorkerError) as exc:
        service.resolve_shop_id("missing")

    assert exc.value.error_code == KJVS_PROFILE_NOT_FOUND


def test_missing_profile_map_path_raises_config_error() -> None:
    service = KuaJingVSService(profile_map_path="", http_client=FakeHttpClient())

    with pytest.raises(WorkerError) as exc:
        service.resolve_shop_id("xhs_dev_01")

    assert exc.value.error_code == KJVS_CONFIG_ERROR


def test_list_shops_uses_mock_client() -> None:
    client = FakeHttpClient()
    client.get_responses.append({"shops": [{"shop_id": "1"}]})
    service = KuaJingVSService(api_id="id", api_secret="secret", http_client=client)

    assert service.list_shops() == [{"shop_id": "1"}]
    assert client.gets[0][0].endswith("/shops")
    assert client.gets[0][1] == {"X-Api-Id": "id", "X-Api-Secret": "secret"}


def test_open_and_close_shop_use_mock_client() -> None:
    client = FakeHttpClient()
    client.post_responses.extend([{"status": "opening"}, {"status": "closed"}])
    service = KuaJingVSService(http_client=client)

    assert service.open_shop("123") == {"status": "opening"}
    assert service.close_shop("123") == {"status": "closed"}
    assert client.posts[0][0].endswith("/shops/123/open")
    assert client.posts[1][0].endswith("/shops/123/close")


def test_wait_environment_ready_success() -> None:
    client = FakeHttpClient()
    client.get_responses.extend([{"status": "opening"}, {"status": "ready"}])
    service = KuaJingVSService(poll_interval_seconds=0, http_client=client)

    assert service.wait_environment_ready("123", timeout_seconds=5) == {"status": "ready"}


def test_wait_environment_ready_failed() -> None:
    client = FakeHttpClient()
    client.get_responses.append({"status": "failed", "error_message": "open failed"})
    service = KuaJingVSService(poll_interval_seconds=0, http_client=client)

    with pytest.raises(WorkerError) as exc:
        service.wait_environment_ready("123", timeout_seconds=5)

    assert exc.value.error_code == KJVS_ENV_FAILED
    assert "open failed" in exc.value.error_message


def test_wait_environment_ready_timeout() -> None:
    client = FakeHttpClient()
    client.get_responses.append({"status": "opening"})
    service = KuaJingVSService(poll_interval_seconds=0, http_client=client)

    with pytest.raises(WorkerError) as exc:
        service.wait_environment_ready("123", timeout_seconds=0)

    assert exc.value.error_code == KJVS_ENV_TIMEOUT


def test_invalid_timeout_env_raises_config_error(monkeypatch) -> None:
    monkeypatch.setenv("KJVS_ENV_READY_TIMEOUT_SECONDS", "bad")

    with pytest.raises(WorkerError) as exc:
        KuaJingVSService(http_client=FakeHttpClient())

    assert exc.value.error_code == KJVS_CONFIG_ERROR
