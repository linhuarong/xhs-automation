import json

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService


client = TestClient(app)


def test_prepare_search_handoff_api_returns_active_job_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        workflows_api,
        "yingdao_handoff_service",
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path),
    )
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.post(
        "/api/workflows/xhs/yingdao/local-handoff/search",
        json={
            "job_id": "search-local-001",
            "account_id": "xhs_dev_01",
            "provider_type": "yingdao_local_file_trigger",
            "keyword": "眼影",
            "limit": 20,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "accepted"
    assert body["active_job_path"].endswith("_active_job.json")
    assert "yingdao_local_search_handoff_prepared" in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


def test_prepare_publish_handoff_api_returns_active_job_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        workflows_api,
        "yingdao_handoff_service",
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path),
    )
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.post(
        "/api/workflows/xhs/yingdao/local-handoff/publish",
        json={
            "job_id": "publish-local-001",
            "account_id": "xhs_dev_01",
            "provider_type": "yingdao_local_file_trigger",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "accepted"
    assert body["active_job_path"].endswith("_active_publish_job.json")


def test_get_search_handoff_result_waiting_when_evidence_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        workflows_api,
        "yingdao_handoff_service",
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path),
    )
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.get("/api/workflows/xhs/yingdao/local-handoff/search/search-local-001")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_rpa_result"
    assert body["error_code"] == "XHS_YINGDAO_EVIDENCE_NOT_FOUND"


def test_get_publish_handoff_result_waiting_when_evidence_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        workflows_api,
        "yingdao_handoff_service",
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path),
    )
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.get("/api/workflows/xhs/yingdao/local-handoff/publish/publish-local-001")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_rpa_result"
    assert body["error_code"] == "XHS_YINGDAO_EVIDENCE_NOT_FOUND"


def test_get_search_handoff_result_reads_mock_evidence(tmp_path, monkeypatch) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    job_dir = tmp_path / "queue" / "search" / "jobs" / "search-local-001"
    job_dir.mkdir(parents=True)
    (job_dir / "search_evidence.json").write_text(
        json.dumps({"job_id": "search-local-001", "job_type": "xhs_search", "status": "success"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(workflows_api, "yingdao_handoff_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.get("/api/workflows/xhs/yingdao/local-handoff/search/search-local-001")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_active_handoff_api_returns_current_status(tmp_path, monkeypatch) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    service.prepare_search_handoff(
        {
            "job_id": "search-local-001",
            "account_id": "xhs_dev_01",
            "keyword": "眼影",
            "limit": 20,
        }
    )
    monkeypatch.setattr(workflows_api, "yingdao_handoff_service", service)

    response = client.get("/api/workflows/xhs/yingdao/local-handoff/active")

    body = response.json()
    assert response.status_code == 200
    assert body["search"]["exists"] is True
    assert body["search"]["job_id"] == "search-local-001"
