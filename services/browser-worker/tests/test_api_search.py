from fastapi.testclient import TestClient

from app.api import search as search_api
from app.main import app
from app.schemas import STATUS_SUCCESS, WorkerResult


client = TestClient(app)


class FakeSearchProvider:
    def __init__(self) -> None:
        self.jobs = []

    def search(self, job):
        self.jobs.append(job)
        return WorkerResult(
            job_id=job.job_id,
            status=STATUS_SUCCESS,
            message="rpa search completed",
            evidence_json_path=".local_evidence/api-search-1/search_evidence.json",
            normalized_records=[{"rank": 1, "keyword": job.keyword}],
            items=[{"rank": 1, "title": "result"}],
        )


def test_search_api_uses_provider_router_for_yingdao(monkeypatch) -> None:
    provider = FakeSearchProvider()
    monkeypatch.setattr(search_api, "get_provider", lambda provider_type: provider)

    response = client.post(
        "/api/xhs/search",
        json={
            "job_id": "api-search-1",
            "account_id": "xhs_dev_01",
            "provider_type": "yingdao_rpa",
            "keyword": "\u773c\u5f71",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_SUCCESS
    assert body["evidence_json_path"] == ".local_evidence/api-search-1/search_evidence.json"
    assert body["normalized_records"] == [{"rank": 1, "keyword": "\u773c\u5f71"}]
    assert provider.jobs[0].provider_type == "yingdao_rpa"
