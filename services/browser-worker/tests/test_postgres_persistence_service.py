import json
from pathlib import Path

from app.schemas import XhsPostgresPersistenceRequest
from app.services.postgres_persistence_service import PostgresPersistenceService
from app.utils.errors import (
    XHS_POSTGRES_PAYLOAD_MISSING,
    XHS_POSTGRES_PERSISTENCE_DISABLED,
    XHS_POSTGRES_SENSITIVE_PAYLOAD_DETECTED,
    XHS_POSTGRES_WRITE_FORBIDDEN,
)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(job_type="search", job_id="search-pg-001"):
    if job_type == "search":
        return {
            "schema_version": "1.0",
            "persistence_type": "local_postgres_mock_persistence",
            "job_id": job_id,
            "job_type": "search",
            "account_id": "xhs_dev_01",
            "target_tables": ["xhs_search_evidence", "xhs_search_records", "xhs_task_log", "xhs_workflow_log"],
            "rows": [
                {"table": "xhs_search_evidence", "job_id": job_id, "account_id": "xhs_dev_01", "keyword": "eyeshadow", "evidence_json_path": ".local/replay.json"},
                {"table": "xhs_search_records", "job_id": job_id, "account_id": "xhs_dev_01", "keyword": "eyeshadow", "rank": 1, "title": "note"},
                {"table": "xhs_task_log", "job_id": job_id, "job_type": "search", "account_id": "xhs_dev_01", "status": "mock_persisted"},
                {"table": "xhs_workflow_log", "job_id": job_id, "workflow": "local_persistence_replay", "status": "mock_persisted"},
            ],
            "strict_binding_context": {"binding_status": "strict_matched", "provider_type": "kuaijingvs_yingdao_rpa"},
            "hardened_discovery_reference": {"status": "success"},
            "source_replay_reference": {"source_replay_status": "success"},
            "forbidden_external_write": True,
        }
    return {
        "schema_version": "1.0",
        "persistence_type": "local_postgres_mock_persistence",
        "job_id": job_id,
        "job_type": "publish",
        "account_id": "xhs_dev_01",
        "target_tables": ["xhs_publish_evidence", "xhs_publish_jobs", "xhs_task_log", "xhs_workflow_log"],
        "rows": [
            {"table": "xhs_publish_evidence", "job_id": job_id, "account_id": "xhs_dev_01", "title": "Test title", "evidence_json_path": ".local/replay.json"},
            {"table": "xhs_publish_jobs", "job_id": job_id, "account_id": "xhs_dev_01", "title": "Test title", "publish_mode": "manual_review"},
            {"table": "xhs_task_log", "job_id": job_id, "job_type": "publish", "account_id": "xhs_dev_01", "status": "mock_persisted"},
            {"table": "xhs_workflow_log", "job_id": job_id, "workflow": "local_persistence_replay", "status": "mock_persisted"},
        ],
        "strict_binding_context": {"binding_status": "strict_matched", "provider_type": "kuaijingvs_yingdao_rpa"},
        "hardened_discovery_reference": {"status": "success"},
        "source_replay_reference": {"source_replay_status": "success"},
        "forbidden_external_write": True,
    }


def _service(tmp_path, env=None, db_connect=None):
    return PostgresPersistenceService(worker_root=tmp_path, env=env or {}, db_connect=db_connect)


def test_dry_run_does_not_connect_database(tmp_path) -> None:
    payload_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "search" / "search-pg-001" / "persistence_payload.json"
    _write_json(payload_path, _payload())
    service = _service(tmp_path, db_connect=lambda dsn: (_ for _ in ()).throw(AssertionError("should not connect")))

    result = service.persist_search_replay(
        XhsPostgresPersistenceRequest(job_id="search-pg-001", job_type="search", account_id="xhs_dev_01", dry_run=True)
    )

    assert result.status == "success"
    assert result.rows_planned == 4
    assert result.rows_written == 0
    assert Path(result.plan_path).exists()


def test_write_flag_false_or_disabled_blocks_real_write(tmp_path) -> None:
    payload_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "search" / "search-pg-001" / "persistence_payload.json"
    _write_json(payload_path, _payload())

    write_forbidden = _service(tmp_path, env={"XHS_POSTGRES_PERSISTENCE_ENABLED": "true", "XHS_ALLOW_REAL_POSTGRES_WRITE": "false"})
    forbidden_result = write_forbidden.persist_search_replay(
        XhsPostgresPersistenceRequest(job_id="search-pg-001", job_type="search", account_id="xhs_dev_01", dry_run=False)
    )
    assert forbidden_result.status == "failed"
    assert forbidden_result.error_code == XHS_POSTGRES_WRITE_FORBIDDEN

    disabled = _service(tmp_path, env={"XHS_POSTGRES_PERSISTENCE_ENABLED": "false", "XHS_ALLOW_REAL_POSTGRES_WRITE": "true"})
    disabled_result = disabled.persist_search_replay(
        XhsPostgresPersistenceRequest(job_id="search-pg-001", job_type="search", account_id="xhs_dev_01", dry_run=False)
    )
    assert disabled_result.status == "failed"
    assert disabled_result.error_code == XHS_POSTGRES_PERSISTENCE_DISABLED


def test_missing_payload_and_sensitive_payload_fail(tmp_path) -> None:
    service = _service(tmp_path)
    missing = service.persist_search_replay(
        XhsPostgresPersistenceRequest(job_id="missing-pg", job_type="search", account_id="xhs_dev_01", dry_run=True)
    )
    assert missing.status == "failed"
    assert missing.error_code == XHS_POSTGRES_PAYLOAD_MISSING

    payload_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "search" / "search-pg-001" / "persistence_payload.json"
    sensitive = _payload()
    sensitive["token"] = "abc"
    _write_json(payload_path, sensitive)
    result = service.persist_search_replay(
        XhsPostgresPersistenceRequest(job_id="search-pg-001", job_type="search", account_id="xhs_dev_01", dry_run=True)
    )
    assert result.status == "failed"
    assert result.error_code == XHS_POSTGRES_SENSITIVE_PAYLOAD_DETECTED


def test_search_and_publish_payloads_generate_insert_plan(tmp_path) -> None:
    service = _service(tmp_path)

    search_plan = service.build_search_insert_plan(_payload("search", "search-pg-001"))
    publish_plan = service.build_publish_insert_plan(_payload("publish", "publish-pg-001"))

    assert {item["table"] for item in search_plan} == {"xhs_search_evidence", "xhs_search_records", "xhs_task_log", "xhs_workflow_log"}
    assert {item["table"] for item in publish_plan} == {"xhs_publish_evidence", "xhs_publish_jobs", "xhs_task_log", "xhs_workflow_log"}


def test_search_and_publish_dry_run_results_output_json(tmp_path) -> None:
    search_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "search" / "search-pg-001" / "persistence_payload.json"
    publish_path = tmp_path / ".local_rpa_queue" / "persistence" / "postgres" / "publish" / "publish-pg-001" / "persistence_payload.json"
    _write_json(search_path, _payload("search", "search-pg-001"))
    _write_json(publish_path, _payload("publish", "publish-pg-001"))
    service = _service(tmp_path)

    search = service.persist_search_replay(XhsPostgresPersistenceRequest(job_id="search-pg-001", job_type="search", account_id="xhs_dev_01"))
    publish = service.persist_publish_replay(XhsPostgresPersistenceRequest(job_id="publish-pg-001", job_type="publish", account_id="xhs_dev_01"))

    assert search.status == "success"
    assert publish.status == "success"
    assert Path(search.result_path).exists()
    assert Path(search.summary_path).exists()
    assert Path(publish.result_path).exists()
    assert Path(publish.summary_path).exists()
