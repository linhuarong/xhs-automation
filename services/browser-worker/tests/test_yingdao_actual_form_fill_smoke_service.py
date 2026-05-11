import json

from app.services.yingdao_actual_form_fill_smoke_service import YingdaoActualFormFillSmokeService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService
from app.utils.errors import (
    XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
    XHS_YINGDAO_ACTUAL_FORM_FILL_REAL_ACTION_FORBIDDEN,
    XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING,
    XHS_YINGDAO_ACTUAL_FORM_FILL_VALUE_MISMATCH,
)


def _service(tmp_path):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    html = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    mapping = YingdaoSelectorMappingService(html_sandbox_service=html, worker_root=tmp_path)
    return YingdaoActualFormFillSmokeService(selector_mapping_service=mapping, worker_root=tmp_path)


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False)


def test_prepare_search_actual_fill_writes_package_and_dependencies(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)
    runbook = _load(result.actual_form_fill_runbook_path)

    assert result.status == "waiting_actual_form_fill_result"
    assert result.actual_form_fill_input_path.endswith("actual_form_fill_input.json")
    assert result.actual_form_fill_runbook_path.endswith("actual_form_fill_runbook.json")
    assert result.html_path.endswith("search_sandbox.html")
    assert service.selector_mapping_service.get_mapping_paths("search", "search-actual-fill-001")["mapping_path"]
    assert any(step["action"] == "open_local_html" for step in runbook["steps"])
    assert any(step.get("field_key") == "keyword_input" and step["action"] == "fill" for step in runbook["steps"])
    assert "open_xiaohongshu" not in json.dumps(runbook, ensure_ascii=False)
    assert "open_external_url" not in json.dumps(runbook, ensure_ascii=False)


def test_prepare_publish_actual_fill_writes_safe_runbook(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_publish_actual_fill(
        "publish-actual-fill-001",
        "xhs_dev_01",
        "娴嬭瘯鏍囬",
        "娴嬭瘯姝ｆ枃",
        ["鐪煎奖", "缇庡"],
        [r".local_assets\publish-actual-fill-001\01.png"],
    )
    runbook = _load(result.actual_form_fill_runbook_path)
    runbook_text = json.dumps(runbook, ensure_ascii=False)

    assert result.html_path.endswith("publish_sandbox.html")
    assert any(step.get("field_key") == "title_input" and step["action"] == "fill" for step in runbook["steps"])
    assert any(step.get("field_key") == "body_textarea" and step["action"] == "fill" for step in runbook["steps"])
    assert any(step.get("field_key") == "tags_input" and step["action"] == "fill" for step in runbook["steps"])
    assert "simulate_prepare_publish_button" in runbook_text
    assert "click_publish" not in runbook_text
    assert "click_real_publish" not in runbook_text


def test_verify_waiting_when_trace_or_result_missing(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)

    waiting = service.verify_actual_form_fill("search", "search-actual-fill-001")
    service.write_mock_trace_and_result("search", "search-actual-fill-001")
    paths = service.get_actual_paths("search", "search-actual-fill-001")
    result = _load(paths["result_path"])
    result_path = paths["result_path"]
    trace_path = paths["trace_path"]
    backup = _load(result_path)
    import os

    os.remove(result_path)
    waiting_result = service.verify_actual_form_fill("search", "search-actual-fill-001")
    _write(result_path, backup)

    assert waiting.status == "waiting_actual_form_fill_result"
    assert waiting.summary.trace_exists is False
    assert waiting_result.status == "waiting_actual_form_fill_result"
    assert waiting_result.summary.trace_exists is True
    assert trace_path.endswith("actual_form_fill_trace.json")


def test_mock_write_and_verify_success_for_search_and_publish(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)
    service.prepare_publish_actual_fill("publish-actual-fill-001", "xhs_dev_01", "娴嬭瘯鏍囬", "娴嬭瘯姝ｆ枃", ["鐪煎奖"], [r".local_assets\publish-actual-fill-001\01.png"])

    search_paths = service.write_mock_trace_and_result("search", "search-actual-fill-001")
    publish_paths = service.write_mock_trace_and_result("publish", "publish-actual-fill-001")
    search_verified = service.verify_actual_form_fill("search", "search-actual-fill-001")
    publish_verified = service.verify_actual_form_fill("publish", "publish-actual-fill-001")

    assert search_paths["trace_path"].endswith("actual_form_fill_trace.json")
    assert search_paths["result_path"].endswith("actual_form_fill_result.json")
    assert publish_paths["trace_path"].endswith("actual_form_fill_trace.json")
    assert publish_paths["result_path"].endswith("actual_form_fill_result.json")
    assert search_verified.status == "verified"
    assert search_verified.summary.trace_valid is True
    assert search_verified.summary.result_valid is True
    assert publish_verified.status == "verified"
    assert publish_verified.summary.trace_valid is True
    assert publish_verified.summary.result_valid is True


def test_trace_forbidden_runtime_flags_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)
    service.write_mock_trace_and_result("search", "search-actual-fill-001")
    paths = service.get_actual_paths("search", "search-actual-fill-001")

    for flag in ("opened_external_url", "opened_xhs", "called_external_api", "clicked_real_publish"):
        trace = _load(paths["trace_path"])
        trace["runtime"][flag] = True
        _write(paths["trace_path"], trace)
        verified = service.verify_actual_form_fill("search", "search-actual-fill-001")
        assert verified.status == "failed"
        assert verified.error_code == XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION
        trace["runtime"][flag] = False
        _write(paths["trace_path"], trace)


def test_result_real_action_flags_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)
    service.write_mock_trace_and_result("search", "search-actual-fill-001")
    paths = service.get_actual_paths("search", "search-actual-fill-001")

    for flag in ("real_search_executed", "real_publish_executed"):
        result = _load(paths["result_path"])
        result["result"][flag] = True
        _write(paths["result_path"], result)
        verified = service.verify_actual_form_fill("search", "search-actual-fill-001")
        assert verified.status == "failed"
        assert verified.error_code == XHS_YINGDAO_ACTUAL_FORM_FILL_REAL_ACTION_FORBIDDEN
        result["result"][flag] = False
        _write(paths["result_path"], result)


def test_required_field_missing_and_value_mismatch_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_actual_fill("search-actual-fill-001", "xhs_dev_01", "鐪煎奖", 20)
    service.write_mock_trace_and_result("search", "search-actual-fill-001")
    paths = service.get_actual_paths("search", "search-actual-fill-001")

    trace = _load(paths["trace_path"])
    trace["filled_fields"] = [item for item in trace["filled_fields"] if item["field_key"] != "keyword_input"]
    _write(paths["trace_path"], trace)
    missing = service.verify_actual_form_fill("search", "search-actual-fill-001")
    assert missing.status == "failed"
    assert missing.error_code == XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING

    service.write_mock_trace_and_result("search", "search-actual-fill-001")
    trace = _load(paths["trace_path"])
    trace["filled_fields"][0]["value"] = "wrong"
    _write(paths["trace_path"], trace)
    mismatch = service.verify_actual_form_fill("search", "search-actual-fill-001")
    assert mismatch.status == "failed"
    assert mismatch.error_code == XHS_YINGDAO_ACTUAL_FORM_FILL_VALUE_MISMATCH
