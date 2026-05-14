from pathlib import Path

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.n8n_handshake_service import N8nHandshakeService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch, env=None, http_client=None):
    monkeypatch.setattr(workflows_api, "n8n_handshake_service", N8nHandshakeService(worker_root=tmp_path, env=env or {}, http_client=http_client))
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_n8n_handshake_ping_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/n8n-handshake/ping",
        json={"handshake_id": "n8n-handshake-api-001", "job_id": "job-api-001"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["dry_run"] is True
    assert body["request_path"].endswith("n8n_handshake_request.json")
    assert Path(body["response_path"]).exists()
    assert Path(body["summary_path"]).exists()


def test_n8n_handshake_search_publish_full_api_return_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    search = client.post(
        "/api/workflows/xhs/n8n-handshake/search",
        json={"handshake_id": "n8n-handshake-search-api", "job_id": "search-api", "account_id": "xhs_dev_01"},
    ).json()
    publish = client.post(
        "/api/workflows/xhs/n8n-handshake/publish",
        json={"handshake_id": "n8n-handshake-publish-api", "job_id": "publish-api", "account_id": "xhs_dev_01"},
    ).json()
    full = client.post(
        "/api/workflows/xhs/n8n-handshake/full",
        json={"handshake_id": "n8n-handshake-full-api", "job_id": "full-api", "account_id": "xhs_dev_01"},
    ).json()

    assert search["status"] == "success"
    assert publish["job_type"] == "publish"
    assert full["job_type"] == "full"
    assert Path(search["summary_path"]).exists()
    assert Path(publish["summary_path"]).exists()
    assert Path(full["summary_path"]).exists()


def test_n8n_handshake_api_fail_safe_for_real_without_env(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/n8n-handshake/ping",
        json={
            "handshake_id": "n8n-handshake-real-fail-api",
            "job_id": "job-real-fail-api",
            "dry_run": False,
            "webhook_url": "https://n8n.example/webhook/test",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "failed"
    assert body["error_code"] == "N8N_HANDSHAKE_DISABLED"


def test_n8n_handshake_api_uses_fake_http_for_real_handshake(tmp_path, monkeypatch) -> None:
    def fake_http(_method, _url, _headers, body, _timeout):
        return {"http_status": 200, "body": {"handshake_id": body["handshake_id"], "dry_run": False, "marker": "XHS_N8N_HANDSHAKE_SMOKE"}}

    _patch_service(
        tmp_path,
        monkeypatch,
        env={"XHS_N8N_HANDSHAKE_ENABLED": "true", "XHS_ALLOW_REAL_N8N_HANDSHAKE": "true"},
        http_client=fake_http,
    )

    body = client.post(
        "/api/workflows/xhs/n8n-handshake/ping",
        json={
            "handshake_id": "n8n-handshake-real-api",
            "job_id": "job-real-api",
            "dry_run": False,
            "webhook_url": "https://n8n.example/webhook/test?key=super-secret",
        },
    ).json()

    assert body["status"] == "success"
    assert body["external_call_made"] is True
    summary_text = Path(body["summary_path"]).read_text(encoding="utf-8")
    assert "super-secret" not in summary_text
