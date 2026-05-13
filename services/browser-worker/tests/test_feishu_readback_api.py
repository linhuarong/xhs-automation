from pathlib import Path

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.feishu_write_service import FeishuWriteService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    monkeypatch.setattr(workflows_api, "feishu_write_service", FeishuWriteService(worker_root=tmp_path, env={}))
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_feishu_readback_search_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/feishu-readback/search",
        json={
            "job_id": "search-readback-api-001",
            "account_id": "xhs_dev_01",
            "records": [{"keyword": "XHS_SMOKE Task45", "title": "XHS_SMOKE title"}],
            "dry_run": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["dry_run"] is True
    assert body["summary_path"].endswith("feishu_readback_summary.json")
    assert Path(body["check_path"]).exists()


def test_feishu_readback_publish_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/feishu-readback/publish",
        json={
            "job_id": "publish-readback-api-001",
            "account_id": "xhs_dev_01",
            "records": [{"title": "XHS_SMOKE Task45", "status": "XHS_SMOKE"}],
            "dry_run": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["job_type"] == "publish"
    assert body["expected_path"].endswith("feishu_readback_expected.json")
