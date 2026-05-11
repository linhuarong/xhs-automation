import json

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.external_readiness_service import ExternalReadinessService
from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.local_e2e_replay_service import LocalE2EReplayService
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
        {"xhs_dev_01": {"shop_id": "123456", "shop_name": "Test Shop 01", "provider_type": "kuaijingvs_yingdao_rpa"}},
    )
    _write_json(
        hardened_path,
        {
            "status": "success",
            "sanitization": {"sensitive_value_scan_passed": True},
            "shops": [{"shop_id": "123456", "shop_name": "Test Shop 01", "provider_type": "kuaijingvs_yingdao_rpa"}],
            "forbidden": {"opened_shop": False, "opened_xhs": False, "called_yingdao_openapi": False},
            "errors": [],
            "evidence_hash": "sha256:test",
        },
    )
    binding = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    binding.hardened_discovery_path = hardened_path
    contract = LocalContractReplayService(account_binding_service=binding, worker_root=tmp_path)
    persistence = LocalPersistenceReplayService(contract_replay_service=contract, account_binding_service=binding, worker_root=tmp_path)
    e2e = LocalE2EReplayService(
        readiness_service=ExternalReadinessService(env={}, worker_root=tmp_path),
        account_binding_service=binding,
        contract_replay_service=contract,
        persistence_replay_service=persistence,
        worker_root=tmp_path,
    )
    monkeypatch.setattr(workflows_api, "xhs_account_binding_service", binding)
    monkeypatch.setattr(workflows_api, "local_contract_replay_service", contract)
    monkeypatch.setattr(workflows_api, "local_persistence_replay_service", persistence)
    monkeypatch.setattr(workflows_api, "local_e2e_replay_service", e2e)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_search_e2e_replay_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    body = client.post(
        "/api/workflows/xhs/e2e-replay/search",
        json={
            "run_id": "e2e-search-api-001",
            "job_id": "search-e2e-api-001",
            "account_id": "xhs_dev_01",
            "keyword": "eyeshadow",
            "limit": 20,
        },
    ).json()

    assert body["status"] == "success"
    assert body["job_type"] == "search"
    assert body["e2e_input_path"].endswith("e2e_input.json")
    assert body["artifacts_manifest_path"].endswith("e2e_artifacts_manifest.json")


def test_publish_e2e_replay_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    body = client.post(
        "/api/workflows/xhs/e2e-replay/publish",
        json={
            "run_id": "e2e-publish-api-001",
            "job_id": "publish-e2e-api-001",
            "account_id": "xhs_dev_01",
            "title": "Test title",
            "body": "Test body",
            "tags": ["eyeshadow", "beauty"],
            "image_paths": [r".local_assets\publish-e2e-api-001\01.png"],
            "publish_mode": "manual_review",
        },
    ).json()

    assert body["status"] == "success"
    assert body["job_type"] == "publish"
    assert any(step["step_name"] == "publish_persistence_replay" for step in body["steps"])


def test_all_e2e_replay_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_services(tmp_path, monkeypatch)

    body = client.post(
        "/api/workflows/xhs/e2e-replay/all",
        json={
            "run_id": "e2e-all-api-001",
            "account_id": "xhs_dev_01",
            "keyword": "eyeshadow",
            "limit": 20,
            "title": "Test title",
            "body": "Test body",
            "tags": ["eyeshadow", "beauty"],
            "image_paths": [r".local_assets\publish-e2e-api-001\01.png"],
            "publish_mode": "manual_review",
        },
    ).json()

    assert body["status"] == "success"
    assert body["job_type"] == "all"
    assert any(step["step_name"] == "search_contract_replay" for step in body["steps"])
    assert any(step["step_name"] == "publish_contract_replay" for step in body["steps"])
