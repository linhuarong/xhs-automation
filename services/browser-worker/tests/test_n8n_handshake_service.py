import json
from pathlib import Path

from app.schemas import XhsN8nHandshakeRequest
from app.services.n8n_handshake_service import N8nHandshakeService


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _service(tmp_path, env=None, http_client=None):
    return N8nHandshakeService(worker_root=tmp_path, env=env or {}, http_client=http_client)


def _assert_no_sensitive_text(*paths: str) -> None:
    text = "\n".join(Path(path).read_text(encoding="utf-8").lower() for path in paths)
    assert "app_secret" not in text
    assert "access_token" not in text
    assert "app_token" not in text
    assert "table_id" not in text
    assert "password" not in text
    assert "cookie" not in text
    assert "super-secret" not in text


def test_default_dry_run_does_not_call_http_and_writes_outputs(tmp_path) -> None:
    def fail_http(*_args, **_kwargs):
        raise AssertionError("HTTP client should not be called in dry-run")

    service = _service(tmp_path, http_client=fail_http)
    response = service.execute_handshake(
        XhsN8nHandshakeRequest(handshake_id="n8n-handshake-001", job_id="job-001", job_type="ping")
    )
    summary = _load(service.get_output_paths("n8n-handshake-001", "ping")["summary_path"])

    assert response.response_valid is True
    assert response.dry_run is True
    assert response.external_call_made is False
    assert summary["status"] == "success"
    assert summary["dry_run"] is True
    assert summary["request_path"].endswith("n8n_handshake_request.json")
    assert Path(summary["response_path"]).exists()
    _assert_no_sensitive_text(summary["request_path"], summary["response_path"], summary["summary_path"])


def test_dry_run_false_without_env_fails_safe(tmp_path) -> None:
    service = _service(tmp_path)
    response = service.execute_handshake(
        XhsN8nHandshakeRequest(
            handshake_id="n8n-handshake-disabled",
            job_id="job-disabled",
            job_type="ping",
            dry_run=False,
            webhook_url="https://n8n.example/webhook/test",
        )
    )

    assert response.response_valid is False
    assert response.error_code == "N8N_HANDSHAKE_DISABLED"
    assert response.external_call_made is False


def test_real_handshake_requires_double_env_and_uses_fake_http(tmp_path) -> None:
    calls = []

    def fake_http(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {
            "http_status": 200,
            "body": {
                "status": "ok",
                "handshake_id": body["handshake_id"],
                "dry_run": False,
                "marker": "XHS_N8N_HANDSHAKE_SMOKE",
            },
        }

    service = _service(
        tmp_path,
        env={
            "XHS_N8N_HANDSHAKE_ENABLED": "true",
            "XHS_ALLOW_REAL_N8N_HANDSHAKE": "true",
            "XHS_N8N_HANDSHAKE_REQUIRE_MARKER": "true",
        },
        http_client=fake_http,
    )
    response = service.execute_handshake(
        XhsN8nHandshakeRequest(
            handshake_id="n8n-handshake-real",
            job_id="job-real",
            job_type="search",
            account_id="xhs_dev_01",
            dry_run=False,
            webhook_url="https://n8n.example/webhook/test?token=super-secret&mode=smoke",
        )
    )
    summary = _load(service.get_output_paths("n8n-handshake-real", "search")["summary_path"])

    assert response.response_valid is True
    assert response.external_call_made is True
    assert len(calls) == 1
    assert summary["webhook_url_redacted"].endswith("token=REDACTED&mode=smoke")
    _assert_no_sensitive_text(summary["request_path"], summary["response_path"], summary["summary_path"])


def test_marker_missing_fails(tmp_path) -> None:
    service = _service(tmp_path)
    response = service.execute_handshake(
        XhsN8nHandshakeRequest(
            handshake_id="n8n-handshake-no-marker",
            job_id="job-no-marker",
            job_type="ping",
            marker="NO_MARKER",
            payload={"note": "missing marker"},
        )
    )

    assert response.error_code == "N8N_HANDSHAKE_MARKER_REQUIRED"


def test_webhook_url_redaction_and_scheme_guards(tmp_path) -> None:
    service = _service(tmp_path)

    assert service.redact_webhook_url("https://n8n.example/webhook?token=abc&sign=def&ok=1").endswith(
        "token=REDACTED&sign=REDACTED&ok=1"
    )
    file_response = service.execute_handshake(
        XhsN8nHandshakeRequest(
            handshake_id="n8n-handshake-file-url",
            job_id="job-file-url",
            job_type="ping",
            dry_run=False,
            webhook_url="file:///tmp/hook",
        )
    )
    js_response = service.execute_handshake(
        XhsN8nHandshakeRequest(
            handshake_id="n8n-handshake-js-url",
            job_id="job-js-url",
            job_type="ping",
            dry_run=False,
            webhook_url="javascript:alert(1)",
        )
    )

    assert file_response.error_code == "N8N_HANDSHAKE_WEBHOOK_URL_BLOCKED"
    assert js_response.error_code == "N8N_HANDSHAKE_WEBHOOK_URL_BLOCKED"


def test_response_handshake_id_and_marker_are_validated(tmp_path) -> None:
    def fake_http(_method, _url, _headers, body, _timeout):
        return {
            "http_status": 200,
            "body": {
                "status": "ok",
                "handshake_id": f"{body['handshake_id']}-wrong",
                "dry_run": False,
                "marker": "XHS_N8N_HANDSHAKE_SMOKE",
            },
        }

    service = _service(
        tmp_path,
        env={"XHS_N8N_HANDSHAKE_ENABLED": "true", "XHS_ALLOW_REAL_N8N_HANDSHAKE": "true"},
        http_client=fake_http,
    )
    response = service.execute_handshake(
        XhsN8nHandshakeRequest(
            handshake_id="n8n-handshake-invalid-response",
            job_id="job-invalid-response",
            dry_run=False,
            webhook_url="https://n8n.example/webhook/test",
        )
    )

    assert response.response_valid is False
    assert response.error_code == "N8N_HANDSHAKE_RESPONSE_INVALID"
