import json

from fastapi.testclient import TestClient

from app.api import publish as publish_api
from app.main import app
from app.schemas import STATUS_FAILED, STATUS_SUCCESS, XhsPublishResult
from app.services.local_rpa_queue import LocalRpaQueueService
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService


client = TestClient(app)


class FakePublishProvider:
    def __init__(self) -> None:
        self.jobs = []

    def publish(self, job):
        self.jobs.append(job)
        if job.title == "失败标题":
            return XhsPublishResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code="MOCK_PUBLISH_FAILED",
                error_message="mock failed",
                evidence_json_path=f".local_evidence/{job.job_id}/publish_evidence.json",
            )
        return XhsPublishResult(
            job_id=job.job_id,
            status=STATUS_SUCCESS,
            note_url="https://example.test/note",
            note_id="note-1",
            evidence_json_path=f".local_evidence/{job.job_id}/publish_evidence.json",
            screenshot_url=f".local_evidence/{job.job_id}/publish_result.png",
        )


def publish_payload(job_id="publish-api-1", title="标题") -> dict:
    return {
        "job_id": job_id,
        "account_id": "xhs_dev_01",
        "provider_type": "kuaijingvs_local_file_trigger_publish",
        "title": title,
        "body": "正文",
        "tags": ["眼影"],
        "assets": [{"local_path": "image.png", "order": 1}],
    }


def test_publish_api_success(monkeypatch) -> None:
    provider = FakePublishProvider()
    monkeypatch.setattr(publish_api, "get_provider", lambda provider_type: provider)

    response = client.post("/api/xhs/publish", json=publish_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == STATUS_SUCCESS
    assert body["note_id"] == "note-1"
    assert provider.jobs[0].provider_type == "kuaijingvs_local_file_trigger_publish"


def test_publish_api_failed(monkeypatch) -> None:
    provider = FakePublishProvider()
    monkeypatch.setattr(publish_api, "get_provider", lambda provider_type: provider)

    response = client.post("/api/xhs/publish", json=publish_payload(title="失败标题"))

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == STATUS_FAILED
    assert body["error_code"] == "MOCK_PUBLISH_FAILED"


def test_publish_batch_partial_failed(monkeypatch) -> None:
    provider = FakePublishProvider()
    monkeypatch.setattr(publish_api, "get_provider", lambda provider_type: provider)

    response = client.post(
        "/api/xhs/publish/batch",
        json={
            "batch_id": "publish-batch-1",
            "account_id": "xhs_dev_01",
            "provider_type": "kuaijingvs_local_file_trigger_publish",
            "jobs": [
                publish_payload("publish-batch-1-ok", "标题"),
                publish_payload("publish-batch-1-fail", "失败标题"),
            ],
            "mode": "sync",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "XHS_PUBLISH_BATCH_PARTIAL_FAILED"
    assert body["success_count"] == 1
    assert body["failed_count"] == 1
    assert body["jobs"][1]["error_code"] == "MOCK_PUBLISH_FAILED"


def test_publish_status_states(tmp_path, monkeypatch) -> None:
    evidence_root = tmp_path / ".local_evidence"
    queue_root = tmp_path / ".local_rpa_jobs"
    monkeypatch.setattr(publish_api, "publish_evidence_service", XhsPublishEvidenceService(evidence_root))
    monkeypatch.setattr(
        publish_api,
        "local_rpa_queue_service",
        LocalRpaQueueService(queue_root=queue_root, evidence_root=evidence_root),
    )

    pending_dir = queue_root / "pending"
    pending_dir.mkdir(parents=True)
    (pending_dir / "_trigger_publish_pending-job.trigger").write_text("pending-job", encoding="utf-8")
    assert client.get("/api/xhs/publish/jobs/pending-job/status").json()["status"] == "pending"

    (evidence_root / "processing-job").mkdir(parents=True)
    assert client.get("/api/xhs/publish/jobs/processing-job/status").json()["status"] == "processing"

    done_dir = evidence_root / "done-job"
    done_dir.mkdir(parents=True)
    (done_dir / "publish_evidence.json").write_text('{"status":"success"}', encoding="utf-8")
    assert client.get("/api/xhs/publish/jobs/done-job/status").json()["status"] == "success"

    body = client.get("/api/xhs/publish/jobs/missing/status").json()
    assert body["status"] == "not_found"
    assert body["error_code"] == "XHS_PUBLISH_JOB_NOT_FOUND"


def test_publish_evidence_api_success_and_not_found(tmp_path, monkeypatch) -> None:
    evidence_root = tmp_path / ".local_evidence"
    job_dir = evidence_root / "publish-1"
    job_dir.mkdir(parents=True)
    (job_dir / "publish_evidence.json").write_text(
        json.dumps({"job_id": "publish-1", "status": "success", "title": "标题"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(publish_api, "publish_evidence_service", XhsPublishEvidenceService(evidence_root))

    success = client.get("/api/xhs/publish/jobs/publish-1/evidence")
    missing = client.get("/api/xhs/publish/jobs/missing/evidence")

    assert success.status_code == 200
    assert success.json()["title"] == "标题"
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "XHS_PUBLISH_EVIDENCE_NOT_FOUND"
