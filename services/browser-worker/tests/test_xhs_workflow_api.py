from fastapi.testclient import TestClient

from app.api import webhooks as webhooks_api
from app.main import app
from app.schemas import XhsWorkflowResult


client = TestClient(app)


class FakeWorkflowService:
    def run_search_to_publish_mock_workflow(self, request):
        return XhsWorkflowResult(
            workflow_id=request.workflow_id,
            status="success",
            search_batch_id=f"{request.workflow_id}-search",
            publish_batch_id=f"{request.workflow_id}-publish",
            search_summary={"success_count": 1},
            publish_summary={"success_count": 1},
            archived_files=[],
            created_at="now",
            finished_at="now",
        )


def test_workflow_api_success(monkeypatch) -> None:
    monkeypatch.setattr(webhooks_api, "workflow_service", FakeWorkflowService())

    response = client.post(
        "/api/xhs/workflows/search-to-publish/mock",
        json={
            "workflow_id": "wf-api",
            "account_id": "xhs_dev_01",
            "keywords": ["眼影"],
            "limit": 20,
            "max_publish_jobs": 1,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["workflow_id"] == "wf-api"
    assert body["status"] == "success"
