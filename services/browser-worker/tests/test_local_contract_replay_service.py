import json
from pathlib import Path

import pytest

from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_CONTRACT_REPLAY_EXTERNAL_CALL_FORBIDDEN,
    XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_MISSING,
    XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_UNSAFE,
    XHS_CONTRACT_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
    XHS_CONTRACT_REPLAY_STRICT_BINDING_FAILED,
    XHS_CONTRACT_REPLAY_STRICT_BINDING_MISSING,
    XHS_CONTRACT_REPLAY_TARGET_UNSUPPORTED,
    WorkerError,
)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _profile(shop_id="123456", shop_name="小红书测试账号01", provider_type="kuaijingvs_yingdao_rpa"):
    return {"xhs_dev_01": {"shop_id": shop_id, "shop_name": shop_name, "provider_type": provider_type}}


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


def _service(tmp_path, prepare_search=True, prepare_publish=True, hardened=None):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    _write_json(profile_path, _profile())
    if hardened is not None:
        _write_json(hardened_path, hardened)
    binding = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    binding.hardened_discovery_path = hardened_path
    if prepare_search:
        binding.prepare_search_strict_binding_check("search-replay-001", "xhs_dev_01", "眼影", 20)
    if prepare_publish:
        binding.prepare_publish_strict_binding_check(
            "publish-replay-001",
            "xhs_dev_01",
            "测试标题",
            "测试正文",
            ["眼影", "美妆"],
            [r".local_assets\publish-replay-001\01.png"],
        )
    return LocalContractReplayService(account_binding_service=binding, worker_root=tmp_path)


def test_prepare_n8n_search_replay_writes_payload_result_summary(tmp_path) -> None:
    service = _service(tmp_path, hardened=_hardened())

    result = service.prepare_n8n_search_replay("search-replay-001", "xhs_dev_01", "眼影", 20)
    payload = _load(result.replay_payload_path)
    replay_result = _load(result.replay_result_path)
    summary = _load(result.replay_summary_path)

    assert result.status == "success"
    assert payload["strict_account_binding"]["binding_status"] == "strict_matched"
    assert payload["hardened_discovery"]["safe"] is True
    assert payload["payload"]["keyword"] == "眼影"
    assert replay_result["real_actions"]["called_external_n8n"] is False
    assert summary["external_calls_made"] is False
    assert "token" not in json.dumps(payload).lower()
    assert "cookie" not in json.dumps(payload).lower()
    assert "secret" not in json.dumps(payload).lower()


def test_prepare_n8n_publish_replay_writes_payload_result_summary(tmp_path) -> None:
    service = _service(tmp_path, hardened=_hardened())

    result = service.prepare_n8n_publish_replay(
        "publish-replay-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影", "美妆"],
        [r".local_assets\publish-replay-001\01.png"],
    )
    payload = _load(result.replay_payload_path)

    assert result.status == "success"
    assert payload["payload"]["event"] == "xhs.publish.requested"
    assert payload["strict_account_binding"]["binding_status"] == "strict_matched"
    assert payload["hardened_discovery"]["evidence_hash"] == "sha256:test"
    assert "token" not in json.dumps(payload).lower()
    assert "cookie" not in json.dumps(payload).lower()
    assert "secret" not in json.dumps(payload).lower()


def test_openclaw_status_replay_writes_expected_context(tmp_path) -> None:
    service = _service(tmp_path, hardened=_hardened())

    result = service.prepare_openclaw_status_replay("publish-replay-001", "xhs_publish", "xhs_dev_01")
    payload = _load(result.replay_payload_path)
    replay_result = _load(result.replay_result_path)

    assert result.status == "success"
    assert payload["expected_status_context"]["strict_binding_status"] == "strict_matched"
    assert payload["expected_status_context"]["workflow_status"] == "local_replay_only"
    assert replay_result["real_actions"]["called_external_openclaw"] is False


def test_replay_fails_when_strict_binding_missing(tmp_path) -> None:
    service = _service(tmp_path, prepare_search=False, prepare_publish=False, hardened=_hardened())

    with pytest.raises(WorkerError) as exc:
        service.prepare_n8n_search_replay("search-replay-001", "xhs_dev_01", "眼影", 20)

    assert exc.value.error_code == XHS_CONTRACT_REPLAY_STRICT_BINDING_MISSING


def test_replay_fails_when_strict_binding_failed(tmp_path) -> None:
    service = _service(tmp_path, hardened=_hardened())
    paths = service.account_binding_service.get_strict_binding_paths("xhs_search", "search-replay-001")
    strict = _load(paths["result_path"])
    strict["binding_status"] = "shop_unmatched"
    strict["status"] = "failed"
    _write_json(paths["result_path"], strict)

    with pytest.raises(WorkerError) as exc:
        service.prepare_n8n_search_replay("search-replay-001", "xhs_dev_01", "眼影", 20)

    assert exc.value.error_code == XHS_CONTRACT_REPLAY_STRICT_BINDING_FAILED


def test_replay_fails_when_hardened_discovery_missing_or_unsafe(tmp_path) -> None:
    missing = _service(tmp_path / "missing", hardened=_hardened())
    Path(missing.account_binding_service.hardened_discovery_path).unlink()
    with pytest.raises(WorkerError) as missing_exc:
        missing.prepare_n8n_search_replay("search-replay-001", "xhs_dev_01", "眼影", 20)
    assert missing_exc.value.error_code == XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_MISSING

    unsafe = _service(tmp_path / "unsafe", hardened=_hardened())
    _write_json(unsafe.account_binding_service.hardened_discovery_path, {**_hardened(status="failed"), "errors": ["unsafe"]})
    with pytest.raises(WorkerError) as unsafe_exc:
        unsafe.prepare_n8n_search_replay("search-replay-001", "xhs_dev_01", "眼影", 20)
    assert unsafe_exc.value.error_code == XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_UNSAFE


def test_sensitive_payload_and_target_guards(tmp_path) -> None:
    service = _service(tmp_path, hardened=_hardened())

    assert service.scan_sensitive_payload({"token": "abc"})["passed"] is False
    assert service.scan_sensitive_payload({"value": "Bearer abc"})["passed"] is False
    with pytest.raises(WorkerError) as sensitive_exc:
        service.replay_to_local_route("n8n_mock_search_webhook", {"cookie": "abc"})
    assert sensitive_exc.value.error_code == XHS_CONTRACT_REPLAY_SENSITIVE_PAYLOAD_DETECTED
    with pytest.raises(WorkerError) as target_exc:
        service.replay_to_local_route("bad_target", {})
    assert target_exc.value.error_code == XHS_CONTRACT_REPLAY_TARGET_UNSUPPORTED
    with pytest.raises(WorkerError) as external_exc:
        service.replay_to_local_route("https://n8n.example/webhook", {})
    assert external_exc.value.error_code == XHS_CONTRACT_REPLAY_EXTERNAL_CALL_FORBIDDEN
