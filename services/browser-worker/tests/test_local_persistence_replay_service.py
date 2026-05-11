import json
from pathlib import Path

import pytest

from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.local_persistence_replay_service import LocalPersistenceReplayService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_MISSING,
    XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_UNSAFE,
    XHS_PERSISTENCE_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
    XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_MISSING,
    XHS_PERSISTENCE_REPLAY_STRICT_BINDING_FAILED,
    XHS_PERSISTENCE_REPLAY_STRICT_BINDING_MISSING,
    WorkerError,
)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _hardened(status="success"):
    return {
        "schema_version": "1.0",
        "evidence_type": "kuaijingvs_readonly_discovery_hardened",
        "status": status,
        "sanitization": {"enabled": True, "sensitive_keys_removed": [], "sensitive_value_scan_passed": True},
        "shop_count": 1,
        "shops": [
            {
                "shop_id": "123456",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
                "raw_keys": ["shop_id", "shop_name"],
                "safe": True,
            }
        ],
        "forbidden": {"opened_shop": False, "opened_xhs": False, "called_yingdao_openapi": False},
        "errors": [],
        "evidence_hash": "sha256:test",
    }


def _service(tmp_path, prepare_contract=True):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    _write_json(
        profile_path,
        {
            "xhs_dev_01": {
                "shop_id": "123456",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        },
    )
    _write_json(hardened_path, _hardened())
    binding = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    binding.hardened_discovery_path = hardened_path
    binding.prepare_search_strict_binding_check("search-persist-001", "xhs_dev_01", "眼影", 20)
    binding.prepare_publish_strict_binding_check(
        "publish-persist-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-persist-001\01.png"],
    )
    contract = LocalContractReplayService(account_binding_service=binding, worker_root=tmp_path)
    if prepare_contract:
        contract.prepare_n8n_search_replay("search-persist-001", "xhs_dev_01", "眼影", 20)
        contract.prepare_n8n_publish_replay(
            "publish-persist-001",
            "xhs_dev_01",
            "测试标题",
            "测试正文",
            ["眼影", "美妆"],
            [r".local_assets\publish-persist-001\01.png"],
        )
    return LocalPersistenceReplayService(contract_replay_service=contract, account_binding_service=binding, worker_root=tmp_path)


def test_missing_source_contract_replay_fails(tmp_path) -> None:
    service = _service(tmp_path, prepare_contract=False)

    with pytest.raises(WorkerError) as exc:
        service.replay_feishu_mock("search-persist-001", "search", "xhs_dev_01")

    assert exc.value.error_code == XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_MISSING


def test_missing_strict_binding_fails(tmp_path) -> None:
    service = _service(tmp_path)
    strict_path = service.account_binding_service.get_strict_binding_paths("search", "search-persist-001")["result_path"]
    Path(strict_path).unlink()

    with pytest.raises(WorkerError) as exc:
        service.replay_feishu_mock("search-persist-001", "search", "xhs_dev_01")

    assert exc.value.error_code == XHS_PERSISTENCE_REPLAY_STRICT_BINDING_MISSING


def test_failed_strict_binding_fails(tmp_path) -> None:
    service = _service(tmp_path)
    strict_path = service.account_binding_service.get_strict_binding_paths("search", "search-persist-001")["result_path"]
    strict = _load(strict_path)
    strict["status"] = "failed"
    strict["binding_status"] = "shop_unmatched"
    _write_json(strict_path, strict)

    with pytest.raises(WorkerError) as exc:
        service.replay_feishu_mock("search-persist-001", "search", "xhs_dev_01")

    assert exc.value.error_code == XHS_PERSISTENCE_REPLAY_STRICT_BINDING_FAILED


def test_missing_or_unsafe_hardened_discovery_fails(tmp_path) -> None:
    missing = _service(tmp_path / "missing")
    Path(missing.account_binding_service.hardened_discovery_path).unlink()
    with pytest.raises(WorkerError) as exc:
        missing.replay_feishu_mock("search-persist-001", "search", "xhs_dev_01")
    assert exc.value.error_code == XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_MISSING

    unsafe = _service(tmp_path / "unsafe")
    _write_json(unsafe.account_binding_service.hardened_discovery_path, {**_hardened(status="failed"), "errors": ["unsafe"]})
    with pytest.raises(WorkerError) as unsafe_exc:
        unsafe.replay_feishu_mock("search-persist-001", "search", "xhs_dev_01")
    assert unsafe_exc.value.error_code == XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_UNSAFE


def test_sensitive_payload_scan_blocks_secret_like_fields(tmp_path) -> None:
    service = _service(tmp_path)

    assert service.scan_sensitive_payload({"token": "abc"})["passed"] is False
    assert service.scan_sensitive_payload({"value": "Bearer abc"})["passed"] is False
    with pytest.raises(WorkerError) as exc:
        service.sanitize_persistence_payload({"cookie": "abc"})
    assert exc.value.error_code == XHS_PERSISTENCE_REPLAY_SENSITIVE_PAYLOAD_DETECTED


def test_feishu_search_and_publish_mock_payloads_are_generated(tmp_path) -> None:
    service = _service(tmp_path)

    search = service.replay_feishu_mock("search-persist-001", "search", "xhs_dev_01")
    publish = service.replay_feishu_mock("publish-persist-001", "publish", "xhs_dev_01")
    search_payload = _load(search.payload_path)
    publish_payload = _load(publish.payload_path)

    assert search.status == "success"
    assert search_payload["fields"]["关键词"] == "眼影"
    assert search_payload["forbidden_external_write"] is True
    assert publish.status == "success"
    assert publish_payload["fields"]["标题"] == "测试标题"
    assert publish_payload["fields"]["发布状态"] == "mock_persisted"


def test_postgres_search_and_publish_mock_payloads_are_generated(tmp_path) -> None:
    service = _service(tmp_path)

    search = service.replay_postgres_mock("search-persist-001", "search", "xhs_dev_01")
    publish = service.replay_postgres_mock("publish-persist-001", "publish", "xhs_dev_01")
    search_payload = _load(search.payload_path)
    publish_payload = _load(publish.payload_path)

    assert "xhs_search_evidence" in search_payload["target_tables"]
    assert "xhs_search_records" in search_payload["target_tables"]
    assert "xhs_publish_evidence" in publish_payload["target_tables"]
    assert "xhs_publish_jobs" in publish_payload["target_tables"]


def test_minio_search_and_publish_object_manifests_are_generated(tmp_path) -> None:
    service = _service(tmp_path)

    search = service.replay_minio_mock("search-persist-001", "search", "xhs_dev_01")
    publish = service.replay_minio_mock("publish-persist-001", "publish", "xhs_dev_01")
    search_manifest = _load(search.payload_path)
    publish_manifest = _load(publish.payload_path)

    assert search.payload_path.endswith("object_manifest.json")
    assert any("search_evidence.json" in item["object_key"] for item in search_manifest["objects"])
    assert any("publish_asset_001" in item["object_key"] for item in publish_manifest["objects"])


def test_all_search_and_publish_replay_chain_targets(tmp_path) -> None:
    service = _service(tmp_path)

    search = service.replay_all_for_job("search-persist-001", "search", "xhs_dev_01")
    publish = service.replay_all_for_job("publish-persist-001", "publish", "xhs_dev_01")

    assert search.status == "success"
    assert search.feishu["status"] == "success"
    assert search.postgres["status"] == "success"
    assert search.minio["status"] == "success"
    assert publish.status == "success"
    assert ".local_rpa_queue" in publish.summary_path or "persistence" in publish.summary_path
