import json

from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import (
    XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION,
    XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING,
    XHS_YINGDAO_FORM_SIMULATOR_UNEXPECTED_ACTION,
)


def _service(tmp_path):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    return YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def test_prepare_search_simulator_writes_package(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)

    assert result.status == "waiting_simulator_result"
    assert (tmp_path / "queue" / "simulator" / "search" / "search-sim-001" / "simulator_input.json").exists()
    assert (tmp_path / "queue" / "simulator" / "search" / "search-sim-001" / "form_spec.json").exists()
    assert (tmp_path / "queue" / "simulator" / "search" / "search-sim-001" / "expected_actions.json").exists()


def test_search_form_spec_and_actions_include_keyword(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)

    form_spec = _load(result.form_spec_path)
    expected = _load(result.expected_actions_path)

    assert any(field["field_key"] == "keyword_input" for field in form_spec["fields"])
    assert expected["actions"][0]["field_key"] == "keyword_input"
    assert expected["actions"][0]["value"] == "眼影"


def test_prepare_publish_simulator_writes_package_and_no_click_publish(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_publish_simulator(
        "publish-sim-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-sim-001\01.png"],
    )
    form_spec = _load(result.form_spec_path)
    expected = _load(result.expected_actions_path)

    keys = {field["field_key"] for field in form_spec["fields"]}
    assert {"title_input", "body_textarea", "tags_input", "image_paths_input"}.issubset(keys)
    assert all(action["action"] != "click_publish" for action in expected["actions"])


def test_verify_missing_trace_returns_waiting(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)

    result = service.verify_simulator("search", "search-sim-001")

    assert result.status == "waiting_simulator_result"
    assert result.summary.trace_exists is False


def test_verify_missing_result_returns_waiting(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)
    paths = service.write_mock_trace_and_result("search", "search-sim-001")
    (tmp_path / "queue" / "simulator" / "search" / "search-sim-001" / "simulator_result.json").unlink()

    result = service.verify_simulator("search", "search-sim-001")

    assert paths["trace_path"].endswith("form_fill_trace.json")
    assert result.status == "waiting_simulator_result"
    assert result.summary.trace_valid is True
    assert result.summary.result_exists is False


def test_mock_write_search_and_publish_verify(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)
    service.prepare_publish_simulator("publish-sim-001", "xhs_dev_01", "测试标题", "测试正文", ["眼影"], [])

    search_paths = service.write_mock_trace_and_result("search", "search-sim-001")
    publish_paths = service.write_mock_trace_and_result("publish", "publish-sim-001")
    search_result = service.verify_simulator("search", "search-sim-001")
    publish_result = service.verify_simulator("publish", "publish-sim-001")

    assert search_paths["trace_path"].endswith("form_fill_trace.json")
    assert search_paths["result_path"].endswith("simulator_result.json")
    assert publish_paths["trace_path"].endswith("form_fill_trace.json")
    assert publish_paths["result_path"].endswith("simulator_result.json")
    assert search_result.status == "verified"
    assert search_result.summary.trace_valid is True
    assert search_result.summary.result_valid is True
    assert publish_result.status == "verified"
    assert publish_result.summary.trace_valid is True
    assert publish_result.summary.result_valid is True


def test_trace_forbidden_runtime_flags_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_trace_and_result("search", "search-sim-001")
    paths = service.get_simulator_paths("search", "search-sim-001")

    for flag in ("opened_browser", "opened_xhs", "called_external_api", "clicked_real_publish"):
        trace = _load(paths["trace_path"])
        trace["runtime"][flag] = True
        with open(paths["trace_path"], "w", encoding="utf-8") as file:
            json.dump(trace, file)
        result = service.verify_simulator("search", "search-sim-001")
        assert result.status == "failed"
        assert result.error_code == XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION
        trace["runtime"][flag] = False
        with open(paths["trace_path"], "w", encoding="utf-8") as file:
            json.dump(trace, file)


def test_publish_trace_click_publish_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_publish_simulator("publish-sim-001", "xhs_dev_01", "测试标题", "测试正文", [], [])
    service.write_mock_trace_and_result("publish", "publish-sim-001")
    paths = service.get_simulator_paths("publish", "publish-sim-001")
    trace = _load(paths["trace_path"])
    trace["actions"].append({"step": 99, "action": "click_publish", "field_key": "publish_button", "value": None})
    with open(paths["trace_path"], "w", encoding="utf-8") as file:
        json.dump(trace, file)

    result = service.verify_simulator("publish", "publish-sim-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION


def test_required_field_missing_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_trace_and_result("search", "search-sim-001")
    paths = service.get_simulator_paths("search", "search-sim-001")
    trace = _load(paths["trace_path"])
    trace["actions"] = trace["actions"][:-1]
    with open(paths["trace_path"], "w", encoding="utf-8") as file:
        json.dump(trace, file)

    result = service.verify_simulator("search", "search-sim-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING


def test_unexpected_action_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_simulator("search-sim-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_trace_and_result("search", "search-sim-001")
    paths = service.get_simulator_paths("search", "search-sim-001")
    trace = _load(paths["trace_path"])
    trace["actions"][0]["field_key"] = "unexpected"
    with open(paths["trace_path"], "w", encoding="utf-8") as file:
        json.dump(trace, file)

    result = service.verify_simulator("search", "search-sim-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_FORM_SIMULATOR_UNEXPECTED_ACTION
