import json

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.local_contract_replay_service import LocalContractReplayService
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
        {
            "xhs_dev_01": {
                "shop_id": "123456",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        },
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
    binding.prepare_search_strict_binding_check("search-replay-001", "xhs_dev_01", "眼影", 20)
    binding.prepare_publish_strict_binding_check(
        "publish-replay-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-replay-001\01.png"],
    )
    replay = LocalContractReplayService(account_binding_service=binding, worker_root=tmp_path)
    monkeypatch.setattr(workflows_api, "xhs_account_binding_service", binding)
    monkeypatch.setattr(workflows_api, "local_contract_replay_service", replay)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return replay


def test_n8n_search_replay_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/contract-replay/n8n/search",
        json={"job_id": "search-replay-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["target"] == "n8n_mock_search_webhook"
    assert body["replay_payload_path"].endswith("replay_payload.json")
    assert body["replay_result_path"].endswith("replay_result.json")
    assert body["replay_summary_path"].endswith("replay_summary.json")


def test_n8n_publish_replay_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/contract-replay/n8n/publish",
        json={
            "job_id": "publish-replay-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影", "美妆"],
            "image_paths": [r".local_assets\publish-replay-001\01.png"],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["target"] == "n8n_mock_publish_webhook"
    assert body["local_route"] == "/api/webhooks/n8n/xhs/publish"


def test_openclaw_job_status_replay_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/contract-replay/openclaw/job-status",
        json={"job_id": "publish-replay-001", "job_type": "xhs_publish", "account_id": "xhs_dev_01"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["target"] == "openclaw_mock_job_status"
    assert body["local_route"] == "/api/webhooks/openclaw/xhs/job-status"


def test_replay_all_search_and_publish_api_return_stable_structure(tmp_path, monkeypatch) -> None:
    replay = _patch_services(tmp_path, monkeypatch)
    binding = replay.account_binding_service
    # all/* creates strict checks for these new job IDs before replaying.
    binding.prepare_search_strict_binding_check("search-replay-all-001", "xhs_dev_01", "眼影", 20)
    binding.prepare_publish_strict_binding_check(
        "publish-replay-all-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影"],
        [r".local_assets\publish-replay-all-001\01.png"],
    )

    search = client.post(
        "/api/workflows/xhs/contract-replay/all/search",
        json={"job_id": "search-replay-all-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    ).json()
    publish = client.post(
        "/api/workflows/xhs/contract-replay/all/publish",
        json={
            "job_id": "publish-replay-all-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [r".local_assets\publish-replay-all-001\01.png"],
        },
    ).json()

    assert search["status"] == "success"
    assert search["n8n_replay"]["status"] == "success"
    assert search["openclaw_replay"]["status"] == "success"
    assert publish["status"] == "success"
    assert publish["n8n_replay"]["status"] == "success"
    assert publish["openclaw_replay"]["status"] == "success"
