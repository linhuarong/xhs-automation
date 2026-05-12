import json
from pathlib import Path

from app.schemas import XhsFeishuWriteRequest
from app.services.feishu_write_service import FeishuWriteService


def _service(tmp_path, env=None, http_client=None):
    return FeishuWriteService(worker_root=tmp_path, env=env or {}, http_client=http_client)


def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_default_dry_run_does_not_write_feishu(tmp_path) -> None:
    def fail_http(*_args, **_kwargs):
        raise AssertionError("Feishu HTTP client should not be called in dry-run")

    service = _service(tmp_path, http_client=fail_http)
    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-001",
            job_type="search",
            account_id="xhs_dev_01",
            records=[{"keyword": "眼影", "title": "测试标题"}],
        )
    )

    payload = _read_json(result.payload_path)
    summary = _read_json(result.summary_path)
    assert result.status == "success"
    assert result.dry_run is True
    assert result.written_count == 0
    assert result.real_write_allowed is False
    assert payload["records"][0]["fields"]["关键词"] == "眼影"
    assert summary["written_count"] == 0


def test_dry_run_false_without_env_is_fail_safe(tmp_path) -> None:
    service = _service(tmp_path, env={})
    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-002",
            job_type="search",
            account_id="xhs_dev_01",
            operation="create",
            records=[{"keyword": "眼影"}],
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error_code == "FEISHU_WRITE_DISABLED"
    assert result.written_count == 0


def test_double_switch_must_both_be_enabled_for_real_write(tmp_path) -> None:
    service = _service(
        tmp_path,
        env={
            "XHS_FEISHU_WRITE_ENABLED": "true",
            "XHS_ALLOW_REAL_FEISHU_WRITE": "false",
            "XHS_FEISHU_APP_ID": "app",
            "XHS_FEISHU_APP_SECRET": "secret-placeholder",
            "XHS_FEISHU_APP_TOKEN": "apptoken",
            "XHS_FEISHU_SEARCH_TABLE_ID": "table",
        },
    )
    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-003",
            job_type="search",
            operation="create",
            records=[{"keyword": "眼影"}],
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.real_write_allowed is False
    assert result.error_code == "FEISHU_WRITE_DISABLED"


def test_search_normalized_records_can_generate_feishu_payload(tmp_path) -> None:
    service = _service(tmp_path)
    source = tmp_path / "search_result.json"
    source.write_text(
        json.dumps(
            {
                "normalized_records": [
                    {
                        "job_id": "search-feishu-004",
                        "keyword": "眼影",
                        "rank": 1,
                        "title": "热门笔记",
                        "author": "作者A",
                        "note_url": "https://www.xiaohongshu.com/explore/note-1",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-004",
            job_type="search",
            account_id="xhs_dev_01",
            source_result_path=str(source),
        )
    )
    payload = _read_json(result.payload_path)

    fields = payload["records"][0]["fields"]
    assert fields["任务ID"] == "search-feishu-004"
    assert fields["关键词"] == "眼影"
    assert fields["排名"] == 1
    assert fields["标题"] == "热门笔记"


def test_publish_result_can_generate_feishu_payload(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.plan_or_write_publish(
        XhsFeishuWriteRequest(
            job_id="publish-feishu-001",
            job_type="publish",
            account_id="xhs_dev_01",
            records=[
                {
                    "title": "测试标题",
                    "body": "测试正文" * 20,
                    "tags": ["眼影", "美妆"],
                    "status": "success",
                }
            ],
        )
    )
    payload = _read_json(result.payload_path)
    fields = payload["records"][0]["fields"]

    assert fields["标题"] == "测试标题"
    assert fields["标签"] == "眼影, 美妆"
    assert fields["发布状态"] == "success"
    assert len(fields["正文摘要"]) <= 120


def test_update_requires_feishu_record_id(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.plan_or_write_publish(
        XhsFeishuWriteRequest(
            job_id="publish-feishu-002",
            job_type="publish",
            operation="update",
            records=[{"title": "测试标题"}],
        )
    )

    assert result.status == "failed"
    assert result.error_code == "FEISHU_RECORD_ID_REQUIRED"


def test_create_does_not_require_feishu_record_id(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.plan_or_write_publish(
        XhsFeishuWriteRequest(
            job_id="publish-feishu-003",
            job_type="publish",
            operation="create",
            records=[{"title": "测试标题"}],
        )
    )

    assert result.status == "success"
    assert result.planned_create_count == 1


def test_field_mapping_can_override_default_field_name(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-005",
            job_type="search",
            records=[{"keyword": "眼影"}],
            field_mapping={"keyword": "自定义关键词"},
        )
    )
    payload = _read_json(result.payload_path)

    assert payload["records"][0]["fields"]["自定义关键词"] == "眼影"


def test_sensitive_payload_is_blocked(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-006",
            job_type="search",
            records=[{"keyword": "眼影", "token": "Bearer abc"}],
            field_mapping={"token": "Token"},
        )
    )

    assert result.status == "failed"
    assert result.sensitive_payload_detected is True
    assert result.error_code == "FEISHU_SENSITIVE_VALUE_BLOCKED"


def test_absolute_paths_are_sanitized_before_feishu_fields(tmp_path) -> None:
    service = _service(tmp_path)
    source_path = tmp_path / ".local_evidence" / "search-feishu-007" / "search_evidence.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("{}", encoding="utf-8")

    result = service.plan_or_write_search(
        XhsFeishuWriteRequest(
            job_id="search-feishu-007",
            job_type="search",
            records=[{"evidence_json_path": str(source_path)}],
        )
    )
    payload_text = Path(result.payload_path).read_text(encoding="utf-8")

    assert str(tmp_path) not in payload_text
    assert ".local_evidence/search-feishu-007/search_evidence.json" in payload_text
