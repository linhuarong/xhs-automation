import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.minio_storage_service import MinioStorageService


client = TestClient(app)


def _write(path, content="{}"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _patch_service(tmp_path, monkeypatch):
    monkeypatch.setattr(workflows_api, "minio_storage_service", MinioStorageService(worker_root=tmp_path, env={}))
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_minio_storage_search_api_dry_run_success(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)
    source = _write(tmp_path / ".local_evidence" / "search-api-001" / "search_evidence.json")

    body = client.post(
        "/api/workflows/xhs/minio-storage/search",
        json={
            "job_id": "search-api-001",
            "account_id": "xhs_dev_01",
            "sources": [{"source_path": str(source), "artifact_type": "evidence_json"}],
            "dry_run": True,
        },
    ).json()

    assert body["status"] == "success"
    assert body["dry_run"] is True
    assert body["uploaded_count"] == 0
    assert body["plan_path"].endswith("upload_plan.json")
    assert Path(body["summary_path"]).exists()


def test_minio_storage_publish_api_dry_run_success(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)
    evidence_dir = tmp_path / ".local_evidence" / "publish-api-001"
    _write(evidence_dir / "publish_evidence.json")

    body = client.post(
        "/api/workflows/xhs/minio-storage/publish",
        json={
            "job_id": "publish-api-001",
            "account_id": "xhs_dev_01",
            "evidence_dir": str(evidence_dir),
            "dry_run": True,
        },
    ).json()

    summary = json.loads(Path(body["summary_path"]).read_text(encoding="utf-8"))
    assert body["status"] == "success"
    assert body["job_type"] == "publish"
    assert summary["total_sources"] == 5
