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


def test_feishu_write_search_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/feishu-write/search",
        json={
            "job_id": "search-feishu-api-001",
            "account_id": "xhs_dev_01",
            "records": [{"keyword": "眼影", "title": "热门笔记"}],
            "dry_run": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["written_count"] == 0
    assert body["plan_path"].endswith("feishu_write_plan.json")
    assert body["payload_path"].endswith("feishu_write_payload.json")
    assert Path(body["summary_path"]).exists()


def test_feishu_write_publish_api_returns_paths(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/feishu-write/publish",
        json={
            "job_id": "publish-feishu-api-001",
            "account_id": "xhs_dev_01",
            "records": [{"title": "测试标题", "status": "success"}],
            "dry_run": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["job_type"] == "publish"
    assert body["summary_path"].endswith("feishu_write_summary.json")
