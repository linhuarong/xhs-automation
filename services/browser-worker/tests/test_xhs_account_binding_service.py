import json

from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.services.yingdao_actual_form_fill_smoke_service import YingdaoActualFormFillSmokeService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService
from app.utils.errors import (
    XHS_ACCOUNT_BINDING_FORBIDDEN_ACTION,
    XHS_ACCOUNT_BINDING_REAL_ACTION_FORBIDDEN,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _service(tmp_path, profile_map=None, discovery=None):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    discovery_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
    if profile_map is not None:
        _write_json(profile_path, profile_map)
    if discovery is not None:
        _write_json(discovery_path, discovery)
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    form = YingdaoFormFillSimulatorService(handoff_service=handoff, worker_root=tmp_path)
    html = YingdaoLocalHtmlSandboxService(form_simulator_service=form, worker_root=tmp_path)
    mapping = YingdaoSelectorMappingService(html_sandbox_service=html, worker_root=tmp_path)
    actual = YingdaoActualFormFillSmokeService(selector_mapping_service=mapping, worker_root=tmp_path)
    return XhsAccountBindingService(
        actual_form_fill_service=actual,
        profile_map_path=profile_path,
        discovery_evidence_path=discovery_path,
        worker_root=tmp_path,
    )


def _profile(shop_id="123456", shop_name="小红书测试账号01"):
    return {
        "xhs_dev_01": {
            "shop_id": shop_id,
            "shop_name": shop_name,
            "provider_type": "kuaijingvs_yingdao_rpa",
        }
    }


def _discovery(shop_id="123456", shop_name="小红书测试账号01"):
    return {
        "status": "success",
        "shops": [
            {
                "shop_id": shop_id,
                "shop_name": shop_name,
                "raw_keys": ["shop_id", "shop_name"],
            }
        ],
    }


def test_prepare_search_account_binding_writes_context_and_attaches_input(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _discovery())

    result = service.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)
    context = _load(result.account_binding_context_path)
    actual_input = _load(result.actual_form_fill_input_path)

    assert result.status == "waiting_account_binding_confirmation"
    assert result.binding_status == "matched"
    assert result.account_binding_input_path.endswith("account_binding_input.json")
    assert result.account_binding_context_path.endswith("account_binding_context.json")
    assert context["mapped_profile"]["shop_id"] == "123456"
    assert actual_input["account_binding"]["binding_status"] == "matched"
    assert actual_input["account_binding"]["opened_shop"] is False
    assert actual_input["account_binding"]["opened_xhs"] is False


def test_prepare_publish_account_binding_writes_context_and_attaches_input(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _discovery())

    result = service.prepare_publish_account_binding(
        "publish-binding-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影"],
        [r".local_assets\publish-binding-001\01.png"],
    )
    actual_input = _load(result.actual_form_fill_input_path)

    assert result.binding_status == "matched"
    assert result.account_binding_context_path.endswith("account_binding_context.json")
    assert result.actual_form_fill_input_path.endswith("actual_form_fill_input.json")
    assert actual_input["account_binding"]["shop_id"] == "123456"


def test_profile_map_missing_invalid_and_account_not_found(tmp_path) -> None:
    missing = _service(tmp_path / "missing", None, _discovery())
    missing_result = missing.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    invalid_path = tmp_path / "invalid" / ".config" / "kuaijingvs_profiles.json"
    invalid_path.parent.mkdir(parents=True)
    invalid_path.write_text("{bad", encoding="utf-8")
    invalid = _service(tmp_path / "invalid", None, _discovery())
    invalid.profile_map_path = invalid_path
    invalid_result = invalid.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    account_missing = _service(tmp_path / "account", {"other": _profile()["xhs_dev_01"]}, _discovery())
    account_result = account_missing.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    assert missing_result.binding_status == "profile_map_missing"
    assert missing_result.status == "failed"
    assert invalid_result.binding_status == "profile_map_invalid"
    assert invalid_result.status == "failed"
    assert account_result.binding_status == "account_not_found"
    assert account_result.status == "failed"


def test_discovery_missing_shop_unmatched_and_name_warning(tmp_path) -> None:
    discovery_missing = _service(tmp_path / "discovery-missing", _profile(), None)
    discovery_result = discovery_missing.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    unmatched = _service(tmp_path / "unmatched", _profile("missing-shop"), _discovery("123456"))
    unmatched_result = unmatched.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    warning = _service(tmp_path / "warning", _profile("123456", "profile-name"), _discovery("123456", "discovery-name"))
    warning_result = warning.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)
    warning_context = _load(warning_result.account_binding_context_path)

    assert discovery_result.binding_status == "discovery_missing"
    assert discovery_result.status == "waiting_account_binding_confirmation"
    assert unmatched_result.binding_status == "shop_unmatched"
    assert unmatched_result.status == "failed"
    assert warning_result.binding_status == "warning_name_mismatch"
    assert warning_context["warnings"]


def test_verify_waiting_and_mock_confirm_success(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _discovery())
    service.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)

    waiting = service.verify_account_binding("search", "search-binding-001")
    mock = service.write_mock_confirmation("search", "search-binding-001")
    verified = service.verify_account_binding("search", "search-binding-001")

    assert waiting.status == "waiting_account_binding_confirmation"
    assert waiting.summary.confirmation_exists is False
    assert mock["confirmation_path"].endswith("account_binding_confirmation.json")
    assert verified.status == "verified"
    assert verified.summary.confirmation_valid is True


def test_mock_confirm_publish_success(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _discovery())
    service.prepare_publish_account_binding("publish-binding-001", "xhs_dev_01", "测试标题", "测试正文", ["眼影"], [r".local_assets\publish-binding-001\01.png"])

    service.write_mock_confirmation("publish", "publish-binding-001")
    verified = service.verify_account_binding("publish", "publish-binding-001")

    assert verified.status == "verified"
    assert verified.summary.confirmation_valid is True


def test_confirmation_forbidden_runtime_flags_fail(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _discovery())
    service.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_confirmation("search", "search-binding-001")
    paths = service.get_binding_paths("search", "search-binding-001")

    for flag in (
        "opened_shop",
        "closed_shop",
        "opened_xhs",
        "opened_external_url",
        "called_yingdao_openapi",
        "called_kuaijingvs_open_shop",
    ):
        confirmation = _load(paths["confirmation_path"])
        confirmation["runtime"][flag] = True
        _write_json(__import__("pathlib").Path(paths["confirmation_path"]), confirmation)
        result = service.verify_account_binding("search", "search-binding-001")
        assert result.status == "failed"
        assert result.error_code == XHS_ACCOUNT_BINDING_FORBIDDEN_ACTION
        confirmation["runtime"][flag] = False
        _write_json(__import__("pathlib").Path(paths["confirmation_path"]), confirmation)


def test_confirmation_real_action_flags_fail(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _discovery())
    service.prepare_search_account_binding("search-binding-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_confirmation("search", "search-binding-001")
    paths = service.get_binding_paths("search", "search-binding-001")

    for flag in ("real_search_executed", "real_publish_executed"):
        confirmation = _load(paths["confirmation_path"])
        confirmation["runtime"][flag] = True
        _write_json(__import__("pathlib").Path(paths["confirmation_path"]), confirmation)
        result = service.verify_account_binding("search", "search-binding-001")
        assert result.status == "failed"
        assert result.error_code == XHS_ACCOUNT_BINDING_REAL_ACTION_FORBIDDEN
        confirmation["runtime"][flag] = False
        _write_json(__import__("pathlib").Path(paths["confirmation_path"]), confirmation)
