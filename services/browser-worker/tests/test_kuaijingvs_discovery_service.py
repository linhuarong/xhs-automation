import json

import pytest

from app.services.kuaijingvs_discovery_service import KuaJingVSDiscoveryService
from app.utils.errors import XHS_EXTERNAL_PROFILE_MAP_INVALID, WorkerError


class FakeAdapter:
    api_base_url = "http://127.0.0.1:49709"

    def __init__(self, shops=None, live_readonly_enabled=True):
        self.shops = shops or []
        self.live_readonly_enabled = live_readonly_enabled
        self.calls = []

    def list_shops_readonly(self):
        self.calls.append("list_shops_readonly")
        return self.shops

    def is_live_readonly_enabled(self):
        return self.live_readonly_enabled


def _write_profile_map(tmp_path, payload) -> str:
    path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_discovery_service_validates_legal_profile_map(tmp_path) -> None:
    service = KuaJingVSDiscoveryService(worker_root=tmp_path)

    result = service.validate_profile_map(
        {
            "xhs_dev_01": {
                "shop_id": "123",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        }
    )

    assert result["valid"] is True


def test_discovery_service_load_profile_map_invalid_json(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")
    service = KuaJingVSDiscoveryService(worker_root=tmp_path)

    with pytest.raises(WorkerError) as exc:
        service.load_profile_map(path)

    assert exc.value.error_code == XHS_EXTERNAL_PROFILE_MAP_INVALID


def test_discovery_service_detects_missing_required_fields(tmp_path) -> None:
    service = KuaJingVSDiscoveryService(worker_root=tmp_path)

    result = service.validate_profile_map({"xhs_dev_01": {"shop_id": "123"}})

    assert result["valid"] is False
    assert "missing fields" in result["error_message"]


def test_match_profile_map_to_shops_with_unmatched_and_unmapped() -> None:
    service = KuaJingVSDiscoveryService(worker_root=".")

    result = service.match_profile_map_to_shops(
        {
            "matched": {
                "shop_id": "123",
                "shop_name": "旧名称",
                "provider_type": "kuaijingvs_yingdao_rpa",
            },
            "missing": {
                "shop_id": "999",
                "shop_name": "缺失店铺",
                "provider_type": "kuaijingvs_yingdao_rpa",
            },
        },
        [
            {"shop_id": "123", "shop_name": "新名称", "raw_keys": ["shop_id"]},
            {"shop_id": "456", "shop_name": "未映射店铺", "raw_keys": ["shop_id"]},
        ],
    )

    assert result["matched_accounts"][0]["matched"] is True
    assert result["matched_accounts"][0]["warning"] == "shop_name differs from discovery"
    assert result["unmatched_accounts"][0]["account_id"] == "missing"
    assert result["unmapped_shops"][0]["shop_id"] == "456"


def test_discover_success_saves_utf8_evidence(tmp_path) -> None:
    profile_path = _write_profile_map(
        tmp_path,
        {
            "xhs_dev_01": {
                "shop_id": "123",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        },
    )
    service = KuaJingVSDiscoveryService(
        adapter=FakeAdapter([{"shop_id": "123", "shop_name": "小红书测试账号01", "raw_keys": ["shop_id"]}]),
        profile_map_path=profile_path,
        evidence_root=tmp_path / ".local_evidence",
        worker_root=tmp_path,
    )

    result = service.discover()
    raw = (tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json").read_bytes()
    payload = json.loads(raw.decode("utf-8"))

    assert raw[:3] != b"\xef\xbb\xbf"
    assert result.status == "success"
    assert result.matched_account_count == 1
    assert payload["matched_accounts"][0]["shop_name"] == "小红书测试账号01"


def test_discover_unmatched_account_does_not_fail(tmp_path) -> None:
    profile_path = _write_profile_map(
        tmp_path,
        {
            "xhs_dev_01": {
                "shop_id": "999",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        },
    )
    service = KuaJingVSDiscoveryService(
        adapter=FakeAdapter([{"shop_id": "123", "shop_name": "店铺", "raw_keys": ["shop_id"]}]),
        profile_map_path=profile_path,
        evidence_root=tmp_path / ".local_evidence",
        worker_root=tmp_path,
    )

    result = service.discover()

    assert result.status == "success"
    assert result.unmatched_account_count == 1
    assert result.unmatched_accounts[0].matched is False


def test_discover_invalid_profile_map_returns_failed_result(tmp_path) -> None:
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text("{bad", encoding="utf-8")
    service = KuaJingVSDiscoveryService(
        adapter=FakeAdapter([{"shop_id": "123", "shop_name": "店铺", "raw_keys": ["shop_id"]}]),
        profile_map_path=profile_path,
        evidence_root=tmp_path / ".local_evidence",
        worker_root=tmp_path,
    )

    result = service.discover()

    assert result.status == "failed"
    assert result.error_code == XHS_EXTERNAL_PROFILE_MAP_INVALID
