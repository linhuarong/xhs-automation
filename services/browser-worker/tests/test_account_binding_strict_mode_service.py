import json

from app.services.xhs_account_binding_service import XhsAccountBindingService


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _profile(shop_id="123456", shop_name="小红书测试账号01", provider_type="kuaijingvs_yingdao_rpa"):
    return {
        "xhs_dev_01": {
            "shop_id": shop_id,
            "shop_name": shop_name,
            "provider_type": provider_type,
        }
    }


def _hardened(shop_id="123456", shop_name="小红书测试账号01", status="success"):
    return {
        "schema_version": "1.0",
        "evidence_type": "kuaijingvs_readonly_discovery_hardened",
        "status": status,
        "sanitization": {"enabled": True, "sensitive_keys_removed": [], "sensitive_value_scan_passed": True},
        "shops": [
            {
                "shop_id": shop_id,
                "shop_name": shop_name,
                "normalized_shop_name": shop_name,
                "provider_type": "kuaijingvs_yingdao_rpa",
                "raw_keys": ["shop_id", "shop_name"],
                "safe": True,
                "warnings": [],
            }
        ],
        "errors": [],
        "forbidden": {
            "contains_token": False,
            "contains_cookie": False,
            "contains_secret": False,
            "contains_password": False,
            "contains_auth_header": False,
            "opened_shop": False,
            "opened_xhs": False,
            "called_yingdao_openapi": False,
        },
        "evidence_hash": "sha256:test",
    }


def _service(tmp_path, profile=None, hardened=None):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    if profile is not None:
        _write_json(profile_path, profile)
    if hardened is not None:
        _write_json(hardened_path, hardened)
    service = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    service.hardened_discovery_path = hardened_path
    return service


def test_strict_search_check_writes_input_and_result(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _hardened())

    result = service.prepare_search_strict_binding_check("search-strict-binding-001", "xhs_dev_01", "眼影", 20)
    strict_input = _load(result.strict_binding_input_path)
    strict_result = _load(result.strict_binding_result_path)

    assert result.status == "success"
    assert result.binding_status == "strict_matched"
    assert strict_input["strict_check_type"] == "xhs_account_binding_strict_mode"
    assert strict_result["checks"]["shop_id_matched"] is True
    assert strict_result["real_actions"]["opened_shop"] is False


def test_strict_publish_check_writes_input_and_result(tmp_path) -> None:
    service = _service(tmp_path, _profile(), _hardened())

    result = service.prepare_publish_strict_binding_check(
        "publish-strict-binding-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影"],
        [r".local_assets\publish-strict-binding-001\01.png"],
    )

    assert result.status == "success"
    assert result.strict_binding_input_path.endswith("strict_binding_input.json")
    assert result.strict_binding_result_path.endswith("strict_binding_result.json")


def test_strict_mode_missing_hardened_discovery_fails(tmp_path) -> None:
    service = _service(tmp_path, _profile(), None)

    result = service.prepare_search_strict_binding_check("search-strict-binding-001", "xhs_dev_01", "眼影", 20)

    assert result.status == "failed"
    assert result.binding_status == "hardened_discovery_missing"


def test_strict_mode_profile_map_missing_and_account_missing_fail(tmp_path) -> None:
    missing_profile = _service(tmp_path / "profile-missing", None, _hardened())
    missing_profile_result = missing_profile.prepare_search_strict_binding_check("search-strict-binding-001", "xhs_dev_01", "眼影", 20)
    missing_account = _service(tmp_path / "account-missing", {"other": _profile()["xhs_dev_01"]}, _hardened())
    missing_account_result = missing_account.prepare_search_strict_binding_check("search-strict-binding-001", "xhs_dev_01", "眼影", 20)

    assert missing_profile_result.status == "failed"
    assert missing_profile_result.binding_status == "profile_map_missing"
    assert missing_account_result.status == "failed"
    assert missing_account_result.binding_status == "account_not_found"


def test_strict_mode_shop_name_and_provider_failures(tmp_path) -> None:
    shop_unmatched = _service(tmp_path / "shop", _profile("missing"), _hardened())
    name_mismatch = _service(tmp_path / "name", _profile("123456", "profile-name"), _hardened("123456", "discovery-name"))
    provider_invalid = _service(tmp_path / "provider", _profile(provider_type="bad_provider"), _hardened())

    assert shop_unmatched.prepare_search_strict_binding_check("job-1", "xhs_dev_01", "眼影").binding_status == "shop_unmatched"
    assert name_mismatch.prepare_search_strict_binding_check("job-2", "xhs_dev_01", "眼影").binding_status == "shop_name_mismatch"
    assert provider_invalid.prepare_search_strict_binding_check("job-3", "xhs_dev_01", "眼影").binding_status == "provider_type_invalid"


def test_strict_mode_unsafe_hardened_discovery_fails(tmp_path) -> None:
    unsafe = _hardened(status="failed")
    unsafe["errors"] = ["sensitive value detected"]
    service = _service(tmp_path, _profile(), unsafe)

    result = service.prepare_search_strict_binding_check("search-strict-binding-001", "xhs_dev_01", "眼影", 20)

    assert result.status == "failed"
    assert result.binding_status == "hardened_discovery_unsafe"
