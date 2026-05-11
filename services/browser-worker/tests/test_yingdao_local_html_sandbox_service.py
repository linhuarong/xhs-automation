import json

from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.utils.errors import (
    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_TEXT,
    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_URL,
    XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING,
    XHS_YINGDAO_HTML_SANDBOX_VALUE_MISMATCH,
)


def _service(tmp_path):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    return YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False)


def test_prepare_search_sandbox_writes_html_manifest_and_expected_dom(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)
    html = open(result.html_path, encoding="utf-8").read()

    assert result.status == "waiting_sandbox_result"
    assert result.html_path.endswith("search_sandbox.html")
    assert "keyword_input" in html
    assert "xiaohongshu.com" not in html
    assert "<script src=" not in html.lower()
    assert "<link " not in html.lower()
    assert _load(result.manifest_path)["sandbox_type"] == "local_static_html"
    assert _load(result.expected_dom_path)["required_elements"][0]["id"] == "keyword_input"


def test_prepare_publish_sandbox_writes_safe_html(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_publish_sandbox(
        "publish-sandbox-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-sandbox-001\01.png"],
    )
    html = open(result.html_path, encoding="utf-8").read()
    expected_dom = _load(result.expected_dom_path)

    assert "title_input" in html
    assert "body_textarea" in html
    assert "tags_input" in html
    assert "image_paths_input" in html
    assert "xiaohongshu.com" not in html
    assert "click_publish" not in html
    assert "立即发布" not in html
    assert "<script src=" not in html.lower()
    assert "<link " not in html.lower()
    assert any(item["id"] == "publish_mode_select" for item in expected_dom["required_elements"])


def test_validate_html_safety_rejects_forbidden_url_and_text(tmp_path) -> None:
    service = _service(tmp_path)

    try:
        service.validate_html_safety("<a href='https://xiaohongshu.com'>x</a>")
    except Exception as exc:
        assert exc.error_code == XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_URL
    else:
        raise AssertionError("forbidden URL should fail")

    try:
        service.validate_html_safety("<button>立即发布</button>")
    except Exception as exc:
        assert exc.error_code == XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_TEXT
    else:
        raise AssertionError("forbidden text should fail")


def test_verify_missing_trace_and_result_return_waiting(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)

    waiting_trace = service.verify_sandbox("search", "search-sandbox-001")
    service.write_mock_trace_and_result("search", "search-sandbox-001")
    paths = service.get_sandbox_paths("search", "search-sandbox-001")
    (tmp_path / "queue" / "sandbox" / "search" / "search-sandbox-001" / "sandbox_result.json").unlink()
    waiting_result = service.verify_sandbox("search", "search-sandbox-001")

    assert waiting_trace.status == "waiting_sandbox_result"
    assert waiting_trace.summary.trace_exists is False
    assert paths["trace_path"].endswith("sandbox_trace.json")
    assert waiting_result.status == "waiting_sandbox_result"
    assert waiting_result.summary.trace_valid is True
    assert waiting_result.summary.result_exists is False


def test_mock_write_search_and_publish_verify(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)
    service.prepare_publish_sandbox(
        "publish-sandbox-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影"],
        [r".local_assets\publish-sandbox-001\01.png"],
    )

    search_paths = service.write_mock_trace_and_result("search", "search-sandbox-001")
    publish_paths = service.write_mock_trace_and_result("publish", "publish-sandbox-001")
    search_result = service.verify_sandbox("search", "search-sandbox-001")
    publish_result = service.verify_sandbox("publish", "publish-sandbox-001")

    assert search_paths["trace_path"].endswith("sandbox_trace.json")
    assert search_paths["result_path"].endswith("sandbox_result.json")
    assert publish_paths["trace_path"].endswith("sandbox_trace.json")
    assert publish_paths["result_path"].endswith("sandbox_result.json")
    assert search_result.status == "verified"
    assert search_result.summary.trace_valid is True
    assert search_result.summary.result_valid is True
    assert publish_result.status == "verified"
    assert publish_result.summary.trace_valid is True
    assert publish_result.summary.result_valid is True


def test_trace_forbidden_runtime_flags_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_trace_and_result("search", "search-sandbox-001")
    paths = service.get_sandbox_paths("search", "search-sandbox-001")

    for flag in ("opened_external_url", "opened_xhs", "called_external_api", "clicked_real_publish"):
        trace = _load(paths["trace_path"])
        trace["runtime"][flag] = True
        _write(paths["trace_path"], trace)
        result = service.verify_sandbox("search", "search-sandbox-001")
        assert result.status == "failed"
        assert result.error_code == XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION
        trace["runtime"][flag] = False
        _write(paths["trace_path"], trace)


def test_required_element_missing_and_value_mismatch_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_sandbox("search-sandbox-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_trace_and_result("search", "search-sandbox-001")
    paths = service.get_sandbox_paths("search", "search-sandbox-001")

    trace = _load(paths["trace_path"])
    trace["filled_fields"] = trace["filled_fields"][:-1]
    _write(paths["trace_path"], trace)
    missing = service.verify_sandbox("search", "search-sandbox-001")
    assert missing.status == "failed"
    assert missing.error_code == XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING

    service.write_mock_trace_and_result("search", "search-sandbox-001")
    trace = _load(paths["trace_path"])
    trace["filled_fields"][0]["value"] = "wrong"
    _write(paths["trace_path"], trace)
    mismatch = service.verify_sandbox("search", "search-sandbox-001")
    assert mismatch.status == "failed"
    assert mismatch.error_code == XHS_YINGDAO_HTML_SANDBOX_VALUE_MISMATCH
