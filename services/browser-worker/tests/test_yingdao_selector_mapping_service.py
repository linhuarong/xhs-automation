import json

from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService
from app.utils.errors import (
    XHS_YINGDAO_SELECTOR_MAPPING_ELEMENT_MISSING,
    XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION,
    XHS_YINGDAO_SELECTOR_MAPPING_SELECTOR_EMPTY,
)


def _service(tmp_path):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    html = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    return YingdaoSelectorMappingService(html_sandbox_service=html, worker_root=tmp_path)


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False)


def test_prepare_search_mapping_writes_package(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_search_mapping("search-selector-001", "xhs_dev_01", "眼影", 20)

    assert result.status == "waiting_selector_confirmation"
    assert result.selector_mapping_input_path.endswith("selector_mapping_input.json")
    assert result.selector_mapping_path.endswith("yingdao_selector_mapping.json")
    assert result.action_sequence_path.endswith("yingdao_action_sequence.json")
    assert result.mapping_report_path.endswith("selector_mapping_report.md")


def test_search_mapping_contains_keyword_selector_and_action(tmp_path) -> None:
    service = _service(tmp_path)
    result = service.prepare_search_mapping("search-selector-001", "xhs_dev_01", "眼影", 20)

    mapping = _load(result.selector_mapping_path)
    actions = _load(result.action_sequence_path)
    report = open(result.mapping_report_path, encoding="utf-8").read()
    keyword = next(item for item in mapping["elements"] if item["field_key"] == "keyword_input")

    assert keyword["recommended_selector"] == "#keyword_input"
    assert "#keyword_input" in keyword["selector_candidates"]
    assert "input[name='keyword_input']" in keyword["selector_candidates"]
    assert "//input[@id='keyword_input']" in keyword["selector_candidates"]
    assert actions["actions"][0]["action_type"] == "fill"
    assert actions["actions"][0]["value"] == "眼影"
    assert "xiaohongshu.com" not in report


def test_prepare_publish_mapping_writes_safe_mapping(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_publish_mapping(
        "publish-selector-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-selector-001\01.png"],
    )
    mapping = _load(result.selector_mapping_path)
    actions = _load(result.action_sequence_path)
    report = open(result.mapping_report_path, encoding="utf-8").read()
    keys = {item["field_key"] for item in mapping["elements"]}

    assert {"title_input", "body_textarea", "tags_input", "image_paths_input"}.issubset(keys)
    assert "click_publish" not in json.dumps(actions, ensure_ascii=False)
    assert "xiaohongshu.com" not in report


def test_build_selector_candidates_and_empty_selector_failure(tmp_path) -> None:
    service = _service(tmp_path)

    candidates = service.build_selector_candidates(
        {"tag": "input", "element_id": "keyword_input", "element_name": "keyword_input", "data_testid": "keyword_input"}
    )

    assert "#keyword_input" in candidates
    assert "input[name='keyword_input']" in candidates
    assert "//input[@id='keyword_input']" in candidates
    try:
        service.choose_recommended_selector([])
    except Exception as exc:
        assert exc.error_code == XHS_YINGDAO_SELECTOR_MAPPING_SELECTOR_EMPTY
    else:
        raise AssertionError("empty selector list should fail")


def test_required_element_missing_fails(tmp_path) -> None:
    service = _service(tmp_path)
    sandbox = service.html_sandbox_service.prepare_search_sandbox("search-selector-001", "xhs_dev_01", "眼影", 20)
    html_path = sandbox.html_path
    html = open(html_path, encoding="utf-8").read().replace("keyword_input", "keyword_missing")
    open(html_path, "w", encoding="utf-8").write(html)
    expected_dom = _load(sandbox.expected_dom_path)

    try:
        service.build_selector_mapping("search", "search-selector-001", html_path, expected_dom)
    except Exception as exc:
        assert exc.error_code == XHS_YINGDAO_SELECTOR_MAPPING_ELEMENT_MISSING
    else:
        raise AssertionError("missing required element should fail")


def test_verify_waiting_and_mock_confirm_success(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_mapping("search-selector-001", "xhs_dev_01", "眼影", 20)

    waiting = service.verify_mapping("search", "search-selector-001")
    mock = service.write_mock_confirmation("search", "search-selector-001")
    verified = service.verify_mapping("search", "search-selector-001")

    assert waiting.status == "waiting_selector_confirmation"
    assert waiting.summary.confirmation_exists is False
    assert mock["confirmation_path"].endswith("selector_mapping_confirmation.json")
    assert verified.status == "verified"
    assert verified.summary.confirmation_valid is True


def test_mock_confirm_publish_success(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_publish_mapping("publish-selector-001", "xhs_dev_01", "测试标题", "测试正文", ["眼影"], [r".local_assets\publish-selector-001\01.png"])

    service.write_mock_confirmation("publish", "publish-selector-001")
    verified = service.verify_mapping("publish", "publish-selector-001")

    assert verified.status == "verified"
    assert verified.summary.confirmation_valid is True


def test_confirmation_forbidden_runtime_flags_fail(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_mapping("search-selector-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_confirmation("search", "search-selector-001")
    paths = service.get_mapping_paths("search", "search-selector-001")

    for flag in ("opened_external_url", "opened_xhs", "called_external_api", "clicked_real_publish"):
        confirmation = _load(paths["confirmation_path"])
        confirmation["runtime"][flag] = True
        _write(paths["confirmation_path"], confirmation)
        result = service.verify_mapping("search", "search-selector-001")
        assert result.status == "failed"
        assert result.error_code == XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION
        confirmation["runtime"][flag] = False
        _write(paths["confirmation_path"], confirmation)
