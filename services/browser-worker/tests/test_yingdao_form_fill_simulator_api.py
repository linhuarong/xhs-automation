from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService


client = TestClient(app)


def _patch_service(tmp_path, monkeypatch):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    service = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    monkeypatch.setattr(workflows_api, "yingdao_form_simulator_service", service)
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))
    return service


def test_prepare_search_form_simulator_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/form-simulator/search/prepare",
        json={"job_id": "search-sim-001", "account_id": "xhs_dev_01", "keyword": "眼影", "limit": 20},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_simulator_result"
    assert body["simulator_dir"].endswith("search-sim-001")
    assert body["form_spec_path"].endswith("form_spec.json")
    assert body["expected_actions_path"].endswith("expected_actions.json")


def test_prepare_publish_form_simulator_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    response = client.post(
        "/api/workflows/xhs/yingdao/form-simulator/publish/prepare",
        json={
            "job_id": "publish-sim-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [],
            "publish_mode": "manual_review",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "waiting_simulator_result"
    assert body["simulator_dir"].endswith("publish-sim-001")


def test_verify_search_form_simulator_api_waiting_then_verified(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)

    waiting = client.get("/api/workflows/xhs/yingdao/form-simulator/search/search-sim-001/verify")
    service.write_mock_trace_and_result("search", "search-sim-001")
    verified = client.get("/api/workflows/xhs/yingdao/form-simulator/search/search-sim-001/verify")

    assert waiting.status_code == 200
    assert waiting.json()["status"] == "waiting_simulator_result"
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["summary"]["trace_valid"] is True
    assert verified.json()["summary"]["result_valid"] is True


def test_verify_publish_form_simulator_api_returns_stable_structure(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_publish_simulator("publish-sim-001", "xhs_dev_01", "测试标题", "测试正文", [], [])
    service.write_mock_trace_and_result("publish", "publish-sim-001")

    response = client.get("/api/workflows/xhs/yingdao/form-simulator/publish/publish-sim-001/verify")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "verified"
    assert body["summary"]["opened_browser"] is False
    assert body["summary"]["opened_xhs"] is False


def test_mock_write_form_simulator_api_writes_trace_and_result(tmp_path, monkeypatch) -> None:
    service = _patch_service(tmp_path, monkeypatch)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)

    response = client.post(
        "/api/workflows/xhs/yingdao/form-simulator/search/search-sim-001/mock-write",
        json={"status": "success"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "simulator_result_written"
    assert body["trace_path"].endswith("form_fill_trace.json")
    assert body["result_path"].endswith("simulator_result.json")
