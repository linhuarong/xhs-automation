from fastapi.testclient import TestClient

from app.api import webhooks as webhooks_api
from app.main import app
from app.schemas import XhsBatchKeywordResult, XhsBatchPublishResult
from app.services.xhs_job_registry import InMemoryXhsJobRegistry


client = TestClient(app)


def test_n8n_search_webhook_success(monkeypatch) -> None:
    def fake_batch(request):
        return XhsBatchKeywordResult(
            batch_id=request.batch_id,
            status="success",
            total_keywords=len(request.keywords),
            success_count=len(request.keywords),
            failed_count=0,
            jobs=[{"job_id": f"{request.batch_id}-1", "status": "success"}],
            created_at="now",
            finished_at="now",
        )

    monkeypatch.setattr(webhooks_api, "create_keyword_batch", fake_batch)
    monkeypatch.setattr(webhooks_api, "xhs_job_registry", InMemoryXhsJobRegistry())

    response = client.post(
        "/api/webhooks/n8n/xhs/search",
        json={
            "workflow_id": "wf-search",
            "batch_id": "batch-search",
            "account_id": "xhs_dev_01",
            "provider_type": "kuaijingvs_local_file_trigger",
            "keywords": ["眼影"],
            "limit": 20,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_n8n_publish_webhook_success(monkeypatch) -> None:
    def fake_batch(request):
        return XhsBatchPublishResult(
            batch_id=request.batch_id,
            status="success",
            total_jobs=len(request.jobs),
            success_count=len(request.jobs),
            failed_count=0,
            jobs=[{"job_id": request.jobs[0].job_id, "status": "success"}],
            created_at="now",
            finished_at="now",
        )

    monkeypatch.setattr(webhooks_api, "create_publish_batch", fake_batch)
    monkeypatch.setattr(webhooks_api, "xhs_job_registry", InMemoryXhsJobRegistry())

    response = client.post(
        "/api/webhooks/n8n/xhs/publish",
        json={
            "workflow_id": "wf-publish",
            "batch_id": "batch-publish",
            "account_id": "xhs_dev_01",
            "provider_type": "kuaijingvs_local_file_trigger_publish",
            "jobs": [{"job_id": "publish-1", "title": "标题", "body": "正文", "tags": ["眼影"], "assets": []}],
        },
    )

    assert response.status_code == 200
    assert response.json()["success_count"] == 1


def test_webhook_invalid_payload_returns_422() -> None:
    response = client.post("/api/webhooks/n8n/xhs/search", json={"workflow_id": "missing-fields"})

    assert response.status_code == 422


def test_openclaw_job_status_not_found_and_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(webhooks_api, "xhs_job_registry", InMemoryXhsJobRegistry())

    not_found = client.post(
        "/api/webhooks/openclaw/xhs/job-status",
        json={"job_id": "missing", "job_type": "search"},
    )
    unsupported = client.post(
        "/api/webhooks/openclaw/xhs/job-status",
        json={"job_id": "missing", "job_type": "unknown"},
    )

    assert not_found.status_code == 200
    assert not_found.json()["status"] == "not_found"
    assert unsupported.status_code == 400
    assert unsupported.json()["error_code"] == "XHS_WEBHOOK_UNSUPPORTED_EVENT"


def test_workflow_health_api() -> None:
    response = client.get("/api/workflows/xhs/health")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["external_integrations_mode"] == "mock"
    assert "kuaijingvs_local_file_trigger_publish" in body["supported_provider_types"]
