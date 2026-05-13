import json
from pathlib import Path

from app.schemas import XhsN8nDispatchRequest
from app.services.n8n_dispatch_smoke_service import N8nDispatchSmokeService


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _service(tmp_path, env=None):
    return N8nDispatchSmokeService(worker_root=tmp_path, env=env or {})


def _assert_no_sensitive_text(*paths: str) -> None:
    text = "\n".join(Path(path).read_text(encoding="utf-8").lower() for path in paths)
    assert "app_secret" not in text
    assert "access_token" not in text
    assert "tenant_access_token" not in text
    assert "app_token" not in text
    assert "table_id" not in text
    assert "cookie" not in text


def test_search_dispatch_defaults_to_dry_run_and_writes_outputs(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.execute_local_dry_run_dispatch(
        XhsN8nDispatchRequest(job_id="n8n-search-001", job_type="search", account_id="xhs_dev_01")
    )
    request = _load(result.request_path)
    summary = _load(result.summary_path)

    assert result.status == "success"
    assert result.dry_run is True
    assert result.steps[0].step_name == "search"
    assert result.steps[0].external_calls_made is False
    assert request["dry_run"] is True
    assert request["payload"]["dry_run"] is True
    assert result.request_path.endswith(".local_rpa_queue\\n8n_dispatch\\search\\n8n-search-001\\n8n_dispatch_request.json") or result.request_path.endswith(".local_rpa_queue/n8n_dispatch/search/n8n-search-001/n8n_dispatch_request.json")
    assert summary["forbidden_actions"]["real_n8n_webhook"] is True
    _assert_no_sensitive_text(result.request_path, result.result_path, result.summary_path)


def test_publish_dispatch_defaults_to_dry_run_and_writes_outputs(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.execute_local_dry_run_dispatch(
        XhsN8nDispatchRequest(job_id="n8n-publish-001", job_type="publish", account_id="xhs_dev_01")
    )

    assert result.status == "success"
    assert result.job_type == "publish"
    assert result.steps[0].step_name == "publish"
    assert Path(result.request_path).exists()
    assert Path(result.result_path).exists()
    assert Path(result.summary_path).exists()


def test_dry_run_false_is_rejected_fail_safe(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.execute_local_dry_run_dispatch(
        XhsN8nDispatchRequest(job_id="n8n-fail-001", job_type="search", account_id="xhs_dev_01", dry_run=False)
    )

    assert result.status == "failed"
    assert result.error_code == "N8N_DISPATCH_DRY_RUN_REQUIRED"
    assert result.external_calls_made is False


def test_non_local_base_url_is_blocked(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.execute_local_dry_run_dispatch(
        XhsN8nDispatchRequest(
            job_id="n8n-remote-001",
            job_type="search",
            account_id="xhs_dev_01",
            base_url="https://n8n.example/webhook",
        )
    )

    assert result.status == "failed"
    assert result.error_code == "N8N_DISPATCH_NON_LOCAL_BASE_URL_BLOCKED"


def test_full_dry_run_includes_postgres_minio_feishu_plans(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.execute_local_dry_run_dispatch(
        XhsN8nDispatchRequest(job_id="n8n-full-001", job_type="full", account_id="xhs_dev_01")
    )
    steps = {step.step_name: step for step in result.steps}

    assert result.status == "success"
    assert {"full_dry_run", "search", "publish", "postgres_persistence", "minio_storage", "feishu_write"}.issubset(steps)
    assert steps["postgres_persistence"].response["rows_written"] == 0
    assert steps["minio_storage"].response["dry_run"] is True
    assert steps["feishu_write"].response["dry_run"] is True
    assert steps["feishu_write"].response["written_count"] == 0
    _assert_no_sensitive_text(result.request_path, result.result_path, result.summary_path)


def test_payload_with_secret_is_failed_without_writing_secret(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.execute_local_dry_run_dispatch(
        XhsN8nDispatchRequest(
            job_id="n8n-secret-001",
            job_type="search",
            account_id="xhs_dev_01",
            payload={"app_secret": "should-not-be-written"},
        )
    )
    request_text = Path(result.request_path).read_text(encoding="utf-8")

    assert result.status == "failed"
    assert result.error_code == "N8N_DISPATCH_FAILED"
    assert "should-not-be-written" not in request_text
