import json

from fastapi.testclient import TestClient

from app.api import search as search_api
from app.main import app
from app.services.local_rpa_queue import LocalRpaQueueService
from app.services.xhs_evidence_service import XhsEvidenceService


client = TestClient(app)


def test_normalize_api_success_and_write_back(tmp_path, monkeypatch) -> None:
    evidence_path = tmp_path / "search_evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "keyword": "眼影",
                "items": [{"title": "结果", "like_count": "188"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(search_api, "evidence_service", XhsEvidenceService(tmp_path))

    response = client.post(
        "/api/xhs/search/normalize",
        json={"evidence_json_path": str(evidence_path), "write_back": True},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["normalized_record_count"] == 1
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["normalized_record_count"] == 1


def test_normalize_api_invalid_json(tmp_path, monkeypatch) -> None:
    evidence_path = tmp_path / "search_evidence.json"
    evidence_path.write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(search_api, "evidence_service", XhsEvidenceService(tmp_path))

    response = client.post(
        "/api/xhs/search/normalize",
        json={"evidence_json_path": str(evidence_path), "write_back": False},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "XHS_EVIDENCE_INVALID"


def test_get_job_evidence_returns_normalized_records(tmp_path, monkeypatch) -> None:
    evidence_root = tmp_path / ".local_evidence"
    job_dir = evidence_root / "job-1"
    job_dir.mkdir(parents=True)
    (job_dir / "search_evidence.json").write_text(
        json.dumps({"job_id": "job-1", "items": [{"title": "结果", "like_count": "3k"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(search_api, "evidence_service", XhsEvidenceService(evidence_root))

    response = client.get("/api/xhs/jobs/job-1/evidence")

    body = response.json()
    assert response.status_code == 200
    assert body["job_id"] == "job-1"
    assert body["normalized_records"][0]["like_count"] == 3000


def test_get_job_evidence_not_found(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(search_api, "evidence_service", XhsEvidenceService(tmp_path))

    response = client.get("/api/xhs/jobs/missing/evidence")

    assert response.status_code == 404
    assert response.json()["error_code"] == "XHS_EVIDENCE_NOT_FOUND"


def test_job_status_states(tmp_path, monkeypatch) -> None:
    evidence_root = tmp_path / ".local_evidence"
    queue_root = tmp_path / ".local_rpa_jobs"
    monkeypatch.setattr(search_api, "evidence_service", XhsEvidenceService(evidence_root))
    monkeypatch.setattr(
        search_api,
        "local_rpa_queue_service",
        LocalRpaQueueService(queue_root=queue_root, evidence_root=evidence_root),
    )

    trigger_dir = queue_root / "pending"
    trigger_dir.mkdir(parents=True)
    (trigger_dir / "_trigger_pending-job.trigger").write_text("pending-job", encoding="utf-8")
    assert client.get("/api/xhs/jobs/pending-job/status").json()["status"] == "pending"

    (evidence_root / "processing-job").mkdir(parents=True)
    assert client.get("/api/xhs/jobs/processing-job/status").json()["status"] == "processing"

    evidence_dir = evidence_root / "done-job"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "search_evidence.json").write_text('{"status":"success"}', encoding="utf-8")
    assert client.get("/api/xhs/jobs/done-job/status").json()["status"] == "success"

    body = client.get("/api/xhs/jobs/missing/status").json()
    assert body["status"] == "not_found"
    assert body["error_code"] == "XHS_JOB_NOT_FOUND"
