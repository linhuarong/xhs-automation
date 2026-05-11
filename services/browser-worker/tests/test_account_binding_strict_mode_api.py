import json

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.kuaijingvs_discovery_hardening_service import KuaJingVSDiscoveryHardeningService
from app.services.xhs_account_binding_service import XhsAccountBindingService


client = TestClient(app)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_services(tmp_path, monkeypatch):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    source_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
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
    _write_json(source_path, {"shops": [{"shop_id": "123456", "shop_name": "小红书测试账号01"}]})
    hardening = KuaJingVSDiscoveryHardeningService(worker_root=tmp_path)
    hardening.harden_discovery_evidence()
    binding = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    binding.hardened_discovery_path = hardened_path
    monkeypatch.setattr(workflows_api, "kuaijingvs_hardening_service", hardening)
    monkeypatch.setattr(workflows_api, "xhs_account_binding_service", binding)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_discovery_harden_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/kuaijingvs/discovery/harden",
        json={"source_evidence_path": ".local_evidence/kuaijingvs_discovery/discovery.json"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["hardened_evidence_path"].endswith("hardened_discovery.json")
    assert body["summary_path"].endswith("hardened_discovery_summary.json")
    assert body["evidence_hash"].startswith("sha256:")


def test_strict_check_search_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/account-binding/search/strict-check",
        json={"job_id": "search-strict-binding-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["binding_status"] == "strict_matched"
    assert body["strict_binding_result_path"].endswith("strict_binding_result.json")


def test_strict_check_publish_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/account-binding/publish/strict-check",
        json={
            "job_id": "publish-strict-binding-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影", "美妆"],
            "image_paths": [r".local_assets\publish-strict-binding-001\01.png"],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["binding_status"] == "strict_matched"
