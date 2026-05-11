from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.yingdao_actual_form_fill_smoke_service import YingdaoActualFormFillSmokeService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    html = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    mapping = YingdaoSelectorMappingService(html_sandbox_service=html, worker_root=tmp_path)
    service = YingdaoActualFormFillSmokeService(selector_mapping_service=mapping, worker_root=tmp_path)
    monkeypatch.setattr(workflows_api, "yingdao_actual_form_fill_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return service


def test_prepare_search_actual_form_fill_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/actual-form-fill/search/prepare",
        json={"job_id": "search-actual-fill-001", "account_id": "xhs_dev_01", "keyword": "鐪煎奖", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_actual_form_fill_result"
    assert body["html_uri"].startswith("file://")
    assert body["actual_form_fill_input_path"].endswith("actual_form_fill_input.json")
    assert body["actual_form_fill_runbook_path"].endswith("actual_form_fill_runbook.json")


def test_prepare_publish_actual_form_fill_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/actual-form-fill/publish/prepare",
        json={
            "job_id": "publish-actual-fill-001",
            "account_id": "xhs_dev_01",
            "title": "娴嬭瘯鏍囬",
            "body": "娴嬭瘯姝ｆ枃",
            "tags": ["鐪煎奖"],
            "image_paths": [r".local_assets\publish-actual-fill-001\01.png"],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_actual_form_fill_result"
    assert body["html_path"].endswith("publish_sandbox.html")


def test_verify_search_actual_form_fill_api_waiting_then_verified(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)

    waiting = client.get("/api/workflows/xhs/yingdao/actual-form-fill/search/search-actual-fill-001/verify")
    service.write_mock_trace_and_result("search", "search-actual-fill-001")
    verified = client.get("/api/workflows/xhs/yingdao/actual-form-fill/search/search-actual-fill-001/verify")

    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting_actual_form_fill_result"
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["summary"]["trace_valid"] is True
    assert verified.json()["summary"]["result_valid"] is True


def test_verify_publish_actual_form_fill_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_publish_actual_fill("publish-actual-fill-001", "xhs_dev_01", "娴嬭瘯鏍囬", "娴嬭瘯姝ｆ枃", ["鐪煎奖"], [r".local_assets\publish-actual-fill-001\01.png"])
    service.write_mock_trace_and_result("publish", "publish-actual-fill-001")

    response = client.get("/api/workflows/xhs/yingdao/actual-form-fill/publish/publish-actual-fill-001/verify")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "verified"
    assert body["summary"]["opened_external_url"] is False
    assert body["summary"]["opened_xhs"] is False
    assert body["summary"]["clicked_real_publish"] is False


def test_mock_write_actual_form_fill_api_writes_trace_and_result(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)

    response = client.post(
        "/api/workflows/xhs/yingdao/actual-form-fill/search/search-actual-fill-001/mock-write",
        json={"status": "success"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "actual_form_fill_result_written"
    assert body["trace_path"].endswith("actual_form_fill_trace.json")
    assert body["result_path"].endswith("actual_form_fill_result.json")
