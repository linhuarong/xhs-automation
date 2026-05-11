from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    html = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    service = YingdaoSelectorMappingService(html_sandbox_service=html, worker_root=tmp_path)
    monkeypatch.setattr(workflows_api, "yingdao_selector_mapping_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return service


def test_prepare_search_selector_mapping_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/selector-mapping/search/prepare",
        json={"job_id": "search-selector-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_selector_confirmation"
    assert body["mapping_dir"].endswith("search-selector-001")
    assert body["selector_mapping_path"].endswith("yingdao_selector_mapping.json")
    assert body["action_sequence_path"].endswith("yingdao_action_sequence.json")


def test_prepare_publish_selector_mapping_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/selector-mapping/publish/prepare",
        json={
            "job_id": "publish-selector-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [r".local_assets\publish-selector-001\01.png"],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_selector_confirmation"
    assert body["mapping_report_path"].endswith("selector_mapping_report.md")


def test_verify_search_selector_mapping_api_waiting_then_verified(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_mapping("search-selector-001", "xhs_dev_01", "眼影", 20)

    waiting = client.get("/api/workflows/xhs/yingdao/selector-mapping/search/search-selector-001/verify")
    service.write_mock_confirmation("search", "search-selector-001")
    verified = client.get("/api/workflows/xhs/yingdao/selector-mapping/search/search-selector-001/verify")

    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting_selector_confirmation"
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["summary"]["confirmation_valid"] is True


def test_verify_publish_selector_mapping_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_publish_mapping("publish-selector-001", "xhs_dev_01", "测试标题", "测试正文", ["眼影"], [r".local_assets\publish-selector-001\01.png"])
    service.write_mock_confirmation("publish", "publish-selector-001")

    response = client.get("/api/workflows/xhs/yingdao/selector-mapping/publish/publish-selector-001/verify")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "verified"
    assert body["summary"]["opened_external_url"] is False
    assert body["summary"]["opened_xhs"] is False


def test_mock_confirm_selector_mapping_api_writes_confirmation(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_mapping("search-selector-001", "xhs_dev_01", "眼影", 20)

    response = client.post(
        "/api/workflows/xhs/yingdao/selector-mapping/search/search-selector-001/mock-confirm",
        json={"status": "success"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "selector_mapping_confirmed"
    assert body["confirmation_path"].endswith("selector_mapping_confirmation.json")
