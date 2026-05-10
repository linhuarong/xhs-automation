from fastapi.testclient import TestClient

from app.api import search as search_api
from app.main import app
from app.schemas import STATUS_FAILED, STATUS_SUCCESS, WorkerResult


client = TestClient(app)


class FakeBatchProvider:
    def __init__(self) -> None:
        self.jobs = []

    def search(self, job):
        self.jobs.append(job)
        if job.keyword == "粉底液":
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code="MOCK_FAILED",
                error_message="mock failed",
                evidence_json_path=f".local_evidence/{job.job_id}/search_evidence.json",
            )
        return WorkerResult(
            job_id=job.job_id,
            status=STATUS_SUCCESS,
            evidence_json_path=f".local_evidence/{job.job_id}/search_evidence.json",
            normalized_records=[{"keyword": job.keyword}],
        )


def test_batch_keywords_success(monkeypatch) -> None:
    provider = FakeBatchProvider()
    monkeypatch.setattr(search_api, "get_provider", lambda provider_type: provider)

    response = client.post(
        "/api/xhs/keywords/batch",
        json={
            "batch_id": "xhs-batch-ok",
            "account_id": "xhs_dev_01",
            "provider_type": "kuaijingvs_local_file_trigger",
            "keywords": ["眼影", "睫毛膏"],
            "limit": 20,
            "mode": "sync",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == STATUS_SUCCESS
    assert body["success_count"] == 2
    assert body["failed_count"] == 0
    assert body["jobs"][0]["job_id"] == "xhs-batch-ok-眼影-1"
    assert provider.jobs[0].provider_type == "kuaijingvs_local_file_trigger"


def test_batch_keywords_partial_failed(monkeypatch) -> None:
    provider = FakeBatchProvider()
    monkeypatch.setattr(search_api, "get_provider", lambda provider_type: provider)

    response = client.post(
        "/api/xhs/keywords/batch",
        json={
            "batch_id": "xhs-batch-partial",
            "account_id": "xhs_dev_01",
            "provider_type": "kuaijingvs_local_file_trigger",
            "keywords": ["眼影", "粉底液", "睫毛膏"],
            "limit": 20,
            "mode": "sync",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "XHS_BATCH_PARTIAL_FAILED"
    assert body["success_count"] == 2
    assert body["failed_count"] == 1
    assert body["jobs"][1]["error_code"] == "MOCK_FAILED"
