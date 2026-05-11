from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.yingdao_desktop_smoke_service import YingdaoDesktopSmokeService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    service = YingdaoDesktopSmokeService(handoff_service=handoff, worker_root=tmp_path)
    monkeypatch.setattr(workflows_api, "yingdao_desktop_smoke_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return service


def test_prepare_search_smoke_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/desktop-smoke/search/prepare",
        json={
            "job_id": "search-smoke-001",
            "account_id": "xhs_dev_01",
            "keyword": "眼影",
            "limit": 20,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_desktop_rpa"
    assert body["active_job_path"].endswith("_active_job.json")
    assert body["expected_receipt_path"].endswith("yingdao_smoke_receipt.json")


def test_prepare_publish_smoke_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/desktop-smoke/publish/prepare",
        json={
            "job_id": "publish-smoke-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_desktop_rpa"
    assert body["active_job_path"].endswith("_active_publish_job.json")


def test_verify_search_smoke_api_waiting_then_verified(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)

    waiting = client.get("/api/workflows/xhs/yingdao/desktop-smoke/search/search-smoke-001/verify")
    service.write_mock_receipt_for_local_test("search", "search-smoke-001")
    service.write_mock_evidence_for_local_test("search", "search-smoke-001", "success")
    verified = client.get("/api/workflows/xhs/yingdao/desktop-smoke/search/search-smoke-001/verify")

    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting_desktop_rpa"
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["summary"]["receipt_valid"] is True
    assert verified.json()["summary"]["evidence_valid"] is True


def test_verify_publish_smoke_api_stable_structure(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_publish_smoke("publish-smoke-001", "xhs_dev_01", "测试标题", "测试正文", [], [])
    service.write_mock_receipt_for_local_test("publish", "publish-smoke-001")
    service.write_mock_evidence_for_local_test("publish", "publish-smoke-001", "waiting_manual_review")

    response = client.get("/api/workflows/xhs/yingdao/desktop-smoke/publish/publish-smoke-001/verify")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "verified"
    assert body["summary"]["opened_browser"] is False
    assert body["summary"]["opened_xhs"] is False


def test_mock_write_api_is_local_only_and_writes_files(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)

    response = client.post(
        "/api/workflows/xhs/yingdao/desktop-smoke/search/search-smoke-001/mock-write",
        json={"status": "success"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "evidence_written"
    assert body["receipt_path"].endswith("yingdao_smoke_receipt.json")
    assert body["evidence_path"].endswith("search_evidence.json")
