from pathlib import Path

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.n8n_dispatch_smoke_service import N8nDispatchSmokeService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    monkeypatch.setattr(workflows_api, "n8n_dispatch_smoke_service", N8nDispatchSmokeService(worker_root=tmp_path, env={}))
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_n8n_dispatch_search_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/n8n-dispatch/search",
        json={"job_id": "n8n-search-api-001", "account_id": "xhs_dev_01"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["dry_run"] is True
    assert body["request_path"].endswith("n8n_dispatch_request.json")
    assert Path(body["result_path"]).exists()
    assert Path(body["summary_path"]).exists()


def test_n8n_dispatch_publish_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/n8n-dispatch/publish",
        json={"job_id": "n8n-publish-api-001", "account_id": "xhs_dev_01"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["job_type"] == "publish"
    assert body["steps"][0]["local_route"] == "/api/xhs/publish"


def test_n8n_dispatch_full_dry_run_api_returns_planned_steps(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/n8n-dispatch/full-dry-run",
        json={"job_id": "n8n-full-api-001", "account_id": "xhs_dev_01"},
    )
    body = response.json()
    step_names = {step["step_name"] for step in body["steps"]}

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["job_type"] == "full"
    assert {"postgres_persistence", "minio_storage", "feishu_write"}.issubset(step_names)


def test_n8n_dispatch_api_rejects_dry_run_false(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/n8n-dispatch/search",
        json={"job_id": "n8n-fail-api-001", "account_id": "xhs_dev_01", "dry_run": False},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "failed"
    assert body["error_code"] == "N8N_DISPATCH_DRY_RUN_REQUIRED"
