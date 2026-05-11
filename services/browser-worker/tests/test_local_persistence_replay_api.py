import json

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.local_persistence_replay_service import LocalPersistenceReplayService
from app.services.xhs_account_binding_service import XhsAccountBindingService


client = TestClient(app)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_services(tmp_path, monkeypatch):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    _write_json(
        profile_path,
        {"xhs_dev_01": {"shop_id": "123456", "shop_name": "小红书测试账号01", "provider_type": "kuaijingvs_yingdao_rpa"}},
    )
    _write_json(
        hardened_path,
        {
            "status": "success",
            "sanitization": {"sensitive_value_scan_passed": True},
            "shops": [{"shop_id": "123456", "shop_name": "小红书测试账号01", "provider_type": "kuaijingvs_yingdao_rpa"}],
            "forbidden": {"opened_shop": False, "opened_xhs": False, "called_yingdao_openapi": False},
            "errors": [],
            "evidence_hash": "sha256:test",
        },
    )
    binding = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    binding.hardened_discovery_path = hardened_path
    binding.prepare_search_strict_binding_check("search-persist-api-001", "xhs_dev_01", "眼影", 20)
    binding.prepare_publish_strict_binding_check(
        "publish-persist-api-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-persist-api-001\01.png"],
    )
    contract = LocalContractReplayService(account_binding_service=binding, worker_root=tmp_path)
    contract.prepare_n8n_search_replay("search-persist-api-001", "xhs_dev_01", "眼影", 20)
    contract.prepare_n8n_publish_replay(
        "publish-persist-api-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-persist-api-001\01.png"],
    )
    persistence = LocalPersistenceReplayService(
        contract_replay_service=contract,
        account_binding_service=binding,
        worker_root=tmp_path,
    )
    monkeypatch.setattr(workflows_api, "xhs_account_binding_service", binding)
    monkeypatch.setattr(workflows_api, "local_contract_replay_service", contract)
    monkeypatch.setattr(workflows_api, "local_persistence_replay_service", persistence)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_feishu_search_and_publish_persistence_api_return_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    search = client.post(
        "/api/workflows/xhs/persistence-replay/feishu/search",
        json={"job_id": "search-persist-api-001", "account_id": "xhs_dev_01"},
    ).json()
    publish = client.post(
        "/api/workflows/xhs/persistence-replay/feishu/publish",
        json={"job_id": "publish-persist-api-001", "account_id": "xhs_dev_01"},
    ).json()

    assert search["status"] == "success"
    assert search["target"] == "feishu"
    assert search["payload_path"].endswith("persistence_payload.json")
    assert publish["status"] == "success"


def test_postgres_and_minio_persistence_api_return_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    postgres = client.post(
        "/api/workflows/xhs/persistence-replay/postgres/search",
        json={"job_id": "search-persist-api-001", "account_id": "xhs_dev_01"},
    ).json()
    minio = client.post(
        "/api/workflows/xhs/persistence-replay/minio/publish",
        json={"job_id": "publish-persist-api-001", "account_id": "xhs_dev_01"},
    ).json()

    assert postgres["status"] == "success"
    assert postgres["target"] == "postgres"
    assert minio["status"] == "success"
    assert minio["target"] == "minio"
    assert minio["payload_path"].endswith("object_manifest.json")


def test_all_search_and_publish_persistence_api_return_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    search = client.post(
        "/api/workflows/xhs/persistence-replay/all/search",
        json={"job_id": "search-persist-api-001", "account_id": "xhs_dev_01"},
    ).json()
    publish = client.post(
        "/api/workflows/xhs/persistence-replay/all/publish",
        json={"job_id": "publish-persist-api-001", "account_id": "xhs_dev_01"},
    ).json()

    assert search["status"] == "success"
    assert search["feishu"]["status"] == "success"
    assert search["postgres"]["status"] == "success"
    assert search["minio"]["status"] == "success"
    assert publish["status"] == "success"
