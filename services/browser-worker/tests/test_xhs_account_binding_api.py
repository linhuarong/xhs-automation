import json

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.services.yingdao_actual_form_fill_smoke_service import YingdaoActualFormFillSmokeService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService


client = TestClient(app)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_service(tmp_path, monkeypatch):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    discovery_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
    _write_json(
        profile_path,
        {
            "xhs_dev_01": {
                "shop_id": "123456",
                "shop_name": "小红书测试账号01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        },
    )
    _write_json(discovery_path, {"shops": [{"shop_id": "123456", "shop_name": "小红书测试账号01"}]})
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    html = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    mapping = YingdaoSelectorMappingService(html_sandbox_service=html, worker_root=tmp_path)
    actual = YingdaoActualFormFillSmokeService(selector_mapping_service=mapping, worker_root=tmp_path)
    service = XhsAccountBindingService(
        actual_form_fill_service=actual,
        profile_map_path=profile_path,
        discovery_evidence_path=discovery_path,
        worker_root=tmp_path,
    )
    monkeypatch.setattr(workflows_api, "xhs_account_binding_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return service


def test_prepare_search_account_binding_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/account-binding/search/prepare",
        json={"job_id": "search-binding-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_account_binding_confirmation"
    assert body["binding_status"] == "matched"
    assert body["account_binding_context_path"].endswith("account_binding_context.json")
    assert body["actual_form_fill_input_path"].endswith("actual_form_fill_input.json")


def test_prepare_publish_account_binding_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/account-binding/publish/prepare",
        json={
            "job_id": "publish-binding-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [r".local_assets\publish-binding-001\01.png"],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["binding_status"] == "matched"
    assert body["confirmation_path"].endswith("account_binding_confirmation.json")


def test_verify_search_account_binding_api_waiting_then_verified(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    waiting = client.get("/api/workflows/xhs/account-binding/search/search-binding-001/verify")
    service.write_mock_confirmation("search", "search-binding-001")
    verified = client.get("/api/workflows/xhs/account-binding/search/search-binding-001/verify")

    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting_account_binding_confirmation"
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["summary"]["confirmation_valid"] is True


def test_verify_publish_account_binding_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_publish_account_binding("publish-binding-001", "xhs_dev_01", "测试标题", "测试正文", ["眼影"], [r".local_assets\publish-binding-001\01.png"])
    service.write_mock_confirmation("publish", "publish-binding-001")

    response = client.get("/api/workflows/xhs/account-binding/publish/publish-binding-001/verify")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "verified"
    assert body["summary"]["opened_shop"] is False
    assert body["summary"]["opened_xhs"] is False


def test_mock_confirm_account_binding_api_writes_confirmation(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    response = client.post(
        "/api/workflows/xhs/account-binding/search/search-binding-001/mock-confirm",
        json={"status": "success"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "account_binding_confirmed"
    assert body["confirmation_path"].endswith("account_binding_confirmation.json")
