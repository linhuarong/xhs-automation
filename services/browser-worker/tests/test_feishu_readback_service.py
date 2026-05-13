import json
from pathlib import Path

from app.schemas import XhsFeishuReadbackRequest
from app.services.feishu_write_service import FeishuWriteService


def _service(tmp_path, env=None, http_client=None):
    return FeishuWriteService(worker_root=tmp_path, env=env or {}, http_client=http_client)


def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _safe_env() -> dict[str, str]:
    return {
        "XHS_FEISHU_WRITE_ENABLED": "true",
        "XHS_ALLOW_REAL_FEISHU_WRITE": "true",
        "XHS_FEISHU_SMOKE_ENABLED": "true",
        "XHS_FEISHU_READBACK_ENABLED": "true",
        "XHS_FEISHU_APP_ID": "app",
        "XHS_FEISHU_APP_SECRET": "secret-placeholder",
        "XHS_FEISHU_APP_TOKEN": "app-token-placeholder",
        "XHS_FEISHU_SEARCH_TABLE_ID": "search-table-placeholder",
        "XHS_FEISHU_PUBLISH_TABLE_ID": "publish-table-placeholder",
    }


def test_readback_default_dry_run_writes_expected_outputs(tmp_path) -> None:
    def fail_http(*_args, **_kwargs):
        raise AssertionError("Feishu HTTP client should not be called in readback dry-run")

    service = _service(tmp_path, http_client=fail_http)
    summary = service.readback_search(
        XhsFeishuReadbackRequest(
            job_id="search-readback-001",
            job_type="search",
            account_id="xhs_dev_01",
            records=[{"keyword": "XHS_SMOKE Task45", "title": "XHS_SMOKE title"}],
        )
    )

    expected = _read_json(summary.expected_path)
    check = _read_json(summary.check_path)
    assert summary.status == "success"
    assert summary.dry_run is True
    assert summary.real_readback_allowed is False
    assert "XHS_SMOKE" in json.dumps(expected, ensure_ascii=False)
    assert check["check_passed"] is True


def test_readback_false_without_env_fails_safe(tmp_path) -> None:
    service = _service(tmp_path, env={})
    summary = service.readback_search(
        XhsFeishuReadbackRequest(
            job_id="search-readback-002",
            job_type="search",
            account_id="xhs_dev_01",
            operation="readback",
            feishu_record_id="rec-1",
            records=[{"keyword": "XHS_SMOKE Task45"}],
            dry_run=False,
        )
    )

    assert summary.status == "failed"
    assert summary.error_code == "FEISHU_READBACK_DISABLED"
    assert summary.real_readback_allowed is False


def test_readback_only_requires_record_id(tmp_path) -> None:
    service = _service(tmp_path)
    summary = service.readback_search(
        XhsFeishuReadbackRequest(
            job_id="search-readback-003",
            job_type="search",
            operation="readback",
            records=[{"keyword": "XHS_SMOKE Task45"}],
        )
    )

    assert summary.status == "failed"
    assert summary.error_code == "FEISHU_READBACK_RECORD_ID_REQUIRED"


def test_real_readback_compares_expected_and_actual_fields(tmp_path) -> None:
    calls = []

    def fake_http(method, path, headers, body):
        calls.append((method, path, headers, body))
        if "tenant_access_token" in path:
            return {"tenant_access_token": "fake-token"}
        assert method == "GET"
        assert "/records/rec-1" in path
        return {
            "data": {
                "record": {
                    "record_id": "rec-1",
                    "fields": {
                        "浠诲姟ID": "search-readback-004",
                        "鍏抽敭璇?": "XHS_SMOKE Task45",
                        "璐﹀彿ID": "xhs_dev_01",
                        "Provider": "kuaijingvs_yingdao_rpa",
                        "鏍囬": "XHS_SMOKE title",
                        "鐘舵€?": "dry_run_planned",
                    },
                }
            }
        }

    service = _service(tmp_path, env=_safe_env(), http_client=fake_http)
    summary = service.readback_search(
        XhsFeishuReadbackRequest(
            job_id="search-readback-004",
            job_type="search",
            account_id="xhs_dev_01",
            operation="readback",
            feishu_record_id="rec-1",
            records=[{"keyword": "XHS_SMOKE Task45", "title": "XHS_SMOKE title"}],
            dry_run=False,
        )
    )

    assert summary.status == "success"
    assert summary.check_passed is True
    assert summary.mismatched_field_count == 0
    assert all(call[0] != "DELETE" for call in calls)
    assert all("batch" not in call[1].lower() for call in calls)


def test_actual_record_without_smoke_marker_fails_safe(tmp_path) -> None:
    def fake_http(method, path, headers, body):
        if "tenant_access_token" in path:
            return {"tenant_access_token": "fake-token"}
        return {"data": {"record": {"record_id": "rec-2", "fields": {"浠诲姟ID": "search-readback-005"}}}}

    service = _service(tmp_path, env=_safe_env(), http_client=fake_http)
    summary = service.readback_search(
        XhsFeishuReadbackRequest(
            job_id="search-readback-005",
            job_type="search",
            operation="readback",
            feishu_record_id="rec-2",
            records=[{"keyword": "XHS_SMOKE Task45"}],
            dry_run=False,
        )
    )

    assert summary.status == "failed"
    assert summary.error_code == "FEISHU_READBACK_MARKER_REQUIRED"


def test_compare_expected_vs_actual_detects_missing_mismatch_and_extra(tmp_path) -> None:
    service = _service(tmp_path)
    comparison = service.compare_expected_vs_readback(
        {"A": "1", "B": "2", "C": "3"},
        {"A": "1", "B": "changed", "D": "4"},
    )

    assert comparison["matched_fields"] == ["A"]
    assert comparison["missing_fields"] == ["C"]
    assert comparison["mismatched_fields"] == ["B"]
    assert comparison["extra_fields"] == ["D"]
    assert comparison["check_passed"] is False
