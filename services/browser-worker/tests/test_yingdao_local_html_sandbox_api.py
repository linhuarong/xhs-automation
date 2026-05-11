from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    service = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    monkeypatch.setattr(workflows_api, "yingdao_html_sandbox_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return service


def test_prepare_search_html_sandbox_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/html-sandbox/search/prepare",
        json={"job_id": "search-sandbox-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_sandbox_result"
    assert body["sandbox_dir"].endswith("search-sandbox-001")
    assert body["html_path"].endswith("search_sandbox.html")
    assert body["expected_dom_path"].endswith("sandbox_expected_dom.json")


def test_prepare_publish_html_sandbox_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/html-sandbox/publish/prepare",
        json={
            "job_id": "publish-sandbox-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [r".local_assets\publish-sandbox-001\01.png"],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_sandbox_result"
    assert body["html_path"].endswith("publish_sandbox.html")


def test_verify_search_html_sandbox_api_waiting_then_verified(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)

    waiting = client.get("/api/workflows/xhs/yingdao/html-sandbox/search/search-sandbox-001/verify")
    service.write_mock_trace_and_result("search", "search-sandbox-001")
    verified = client.get("/api/workflows/xhs/yingdao/html-sandbox/search/search-sandbox-001/verify")

    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting_sandbox_result"
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["summary"]["trace_valid"] is True
    assert verified.json()["summary"]["result_valid"] is True


def test_verify_publish_html_sandbox_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_publish_sandbox(
        "publish-sandbox-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影"],
        [r".local_assets\publish-sandbox-001\01.png"],
    )
    service.write_mock_trace_and_result("publish", "publish-sandbox-001")

    response = client.get("/api/workflows/xhs/yingdao/html-sandbox/publish/publish-sandbox-001/verify")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "verified"
    assert body["summary"]["opened_external_url"] is False
    assert body["summary"]["opened_xhs"] is False


def test_mock_write_html_sandbox_api_writes_trace_and_result(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)

    response = client.post(
        "/api/workflows/xhs/yingdao/html-sandbox/search/search-sandbox-001/mock-write",
        json={"status": "success"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "sandbox_result_written"
    assert body["trace_path"].endswith("sandbox_trace.json")
    assert body["result_path"].endswith("sandbox_result.json")
