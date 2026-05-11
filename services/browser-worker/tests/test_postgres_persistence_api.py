import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.postgres_persistence_service import PostgresPersistenceService


client = TestClient(app)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(job_type, job_id):
    if job_type == "search":
        rows = [
            {"table": "xhs_search_evidence", "job_id": job_id, "account_id": "xhs_dev_01", "keyword": "eyeshadow"},
            {"table": "xhs_search_records", "job_id": job_id, "account_id": "xhs_dev_01", "keyword": "eyeshadow", "rank": 1},
            {"table": "xhs_task_log", "job_id": job_id, "job_type": "search", "account_id": "xhs_dev_01"},
            {"table": "xhs_workflow_log", "job_id": job_id, "workflow": "local_persistence_replay", "status": "mock_persisted"},
        ]
    else:
        rows = [
            {"table": "xhs_publish_evidence", "job_id": job_id, "account_id": "xhs_dev_01", "title": "Test title"},
            {"table": "xhs_publish_jobs", "job_id": job_id, "account_id": "xhs_dev_01", "title": "Test title"},
            {"table": "xhs_task_log", "job_id": job_id, "job_type": "publish", "account_id": "xhs_dev_01"},
            {"table": "xhs_workflow_log", "job_id": job_id, "workflow": "local_persistence_replay", "status": "mock_persisted"},
        ]
    return {
        "schema_version": "1.0",
        "persistence_type": "local_postgres_mock_persistence",
        "job_id": job_id,
        "job_type": job_type,
        "account_id": "xhs_dev_01",
        "rows": rows,
        "strict_binding_context": {"binding_status": "strict_matched", "provider_type": "kuaijingvs_yingdao_rpa"},
        "hardened_discovery_reference": {"status": "success"},
        "source_replay_reference": {"source_replay_status": "success"},
        "forbidden_external_write": True,
    }


def _patch_service(tmp_path, monkeypatch):
    search_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "search" / "search-pg-api-001" / "persistence_payload.json"
    publish_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "publish" / "publish-pg-api-001" / "persistence_payload.json"
    _write_json(search_path, _payload("search", "search-pg-api-001"))
    _write_json(publish_path, _payload("publish", "publish-pg-api-001"))
    monkeypatch.setattr(workflows_api, "postgres_persistence_service", PostgresPersistenceService(worker_root=tmp_path, env={}))
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))


def test_postgres_persistence_search_dry_run_api_success(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    body = client.post(
        "/api/workflows/xhs/postgres-persistence/search",
        json={"job_id": "search-pg-api-001", "account_id": "xhs_dev_01", "dry_run": True},
    ).json()

    assert body["status"] == "success"
    assert body["dry_run"] is True
    assert body["rows_planned"] == 4
    assert body["rows_written"] == 0
    assert body["result_path"].endswith("postgres_persistence_result.json")


def test_postgres_persistence_publish_dry_run_api_success(tmp_path, monkeypatch) -> None:
    _patch_service(tmp_path, monkeypatch)

    body = client.post(
        "/api/workflows/xhs/postgres-persistence/publish",
        json={"job_id": "publish-pg-api-001", "account_id": "xhs_dev_01", "dry_run": True},
    ).json()

    assert body["status"] == "success"
    assert body["job_type"] == "publish"
    assert body["target_tables"] == ["xhs_publish_evidence", "xhs_publish_jobs", "xhs_task_log", "xhs_workflow_log"]
