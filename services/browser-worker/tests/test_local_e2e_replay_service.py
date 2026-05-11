import json
from pathlib import Path

from app.services.external_readiness_service import ExternalReadinessService
from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.local_e2e_replay_service import LocalE2EReplayService
from app.services.local_persistence_replay_service import LocalPersistenceReplayService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_E2E_REPLAY_CONTRACT_REPLAY_FAILED,
    XHS_E2E_REPLAY_HARDENED_DISCOVERY_FAILED,
    XHS_E2E_REPLAY_PERSISTENCE_REPLAY_FAILED,
    XHS_E2E_REPLAY_READINESS_FAILED,
    XHS_E2E_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
    XHS_E2E_REPLAY_STRICT_BINDING_FAILED,
)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _hardened(shop_id="123456", shop_name="Test Shop 01", status="success"):
    return {
        "schema_version": "1.0",
        "evidence_type": "kuaijingvs_readonly_discovery_hardened",
        "status": status,
        "sanitization": {"enabled": True, "sensitive_keys_removed": [], "sensitive_value_scan_passed": True},
        "shop_count": 1,
        "shops": [
            {
                "shop_id": shop_id,
                "shop_name": shop_name,
                "normalized_shop_name": shop_name,
                "provider_type": "kuaijingvs_yingdao_rpa",
                "raw_keys": ["shop_id", "shop_name", "provider_type"],
                "safe": True,
            }
        ],
        "forbidden": {"opened_shop": False, "opened_xhs": False, "called_yingdao_openapi": False},
        "errors": [] if status == "success" else ["unsafe"],
        "evidence_hash": "sha256:test",
    }


def _service(tmp_path, profile_shop_id="123456", hardened_status="success"):
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    _write_json(
        profile_path,
        {
            "xhs_dev_01": {
                "shop_id": profile_shop_id,
                "shop_name": "Test Shop 01",
                "provider_type": "kuaijingvs_yingdao_rpa",
            }
        },
    )
    _write_json(hardened_path, _hardened(status=hardened_status))
    binding = XhsAccountBindingService(profile_map_path=profile_path, worker_root=tmp_path)
    binding.hardened_discovery_path = hardened_path
    contract = LocalContractReplayService(account_binding_service=binding, worker_root=tmp_path)
    persistence = LocalPersistenceReplayService(contract_replay_service=contract, account_binding_service=binding, worker_root=tmp_path)
    readiness = ExternalReadinessService(env={}, worker_root=tmp_path)
    return LocalE2EReplayService(
        readiness_service=readiness,
        account_binding_service=binding,
        contract_replay_service=contract,
        persistence_replay_service=persistence,
        worker_root=tmp_path,
    )


def test_search_e2e_replay_generates_all_local_artifacts(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.replay_search("e2e-search-001", "search-e2e-001", "xhs_dev_01", "eyeshadow", 20)
    manifest = _load(result.artifacts_manifest_path)

    assert result.status == "success"
    assert Path(result.e2e_input_path).exists()
    assert Path(result.e2e_result_path).exists()
    assert Path(result.e2e_summary_path).exists()
    assert Path(result.artifacts_manifest_path).exists()
    assert any("replay" in item["path"] for item in manifest["artifacts"])
    assert any("persistence" in item["path"] for item in manifest["artifacts"])


def test_publish_e2e_replay_generates_all_local_artifacts(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.replay_publish(
        "e2e-publish-001",
        "publish-e2e-001",
        "xhs_dev_01",
        "Test title",
        "Test body",
        ["eyeshadow", "beauty"],
        [r".local_assets\publish-e2e-001\01.png"],
    )

    assert result.status == "success"
    assert any(step.step_name == "publish_contract_replay" for step in result.steps)
    assert any(step.step_name == "publish_persistence_replay" for step in result.steps)


def test_all_e2e_replay_runs_search_and_publish(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.replay_all(
        "e2e-all-001",
        "xhs_dev_01",
        "eyeshadow",
        20,
        "Test title",
        "Test body",
        ["eyeshadow", "beauty"],
        [r".local_assets\publish-e2e-001\01.png"],
    )
    steps = [step.step_name for step in result.steps]

    assert result.status == "success"
    assert "search_contract_replay" in steps
    assert "publish_contract_replay" in steps
    assert "search_persistence_replay" in steps
    assert "publish_persistence_replay" in steps


def test_readiness_failure_returns_failed_result(tmp_path) -> None:
    service = _service(tmp_path)

    class FailedReadiness:
        status = "failed"

    service.readiness_service.check_all = lambda: FailedReadiness()
    result = service.replay_search("e2e-readiness-fail", "search-e2e-fail", "xhs_dev_01", "eyeshadow", 20)

    assert result.status == "failed"
    assert result.error_code == XHS_E2E_REPLAY_READINESS_FAILED


def test_strict_binding_failure_returns_failed_result(tmp_path) -> None:
    service = _service(tmp_path, profile_shop_id="999999")

    result = service.replay_search("e2e-strict-fail", "search-e2e-fail", "xhs_dev_01", "eyeshadow", 20)

    assert result.status == "failed"
    assert result.error_code == XHS_E2E_REPLAY_STRICT_BINDING_FAILED


def test_hardened_discovery_unsafe_returns_failed_result(tmp_path) -> None:
    service = _service(tmp_path, hardened_status="failed")

    result = service.replay_search("e2e-hardened-fail", "search-e2e-fail", "xhs_dev_01", "eyeshadow", 20)

    assert result.status == "failed"
    assert result.error_code == XHS_E2E_REPLAY_HARDENED_DISCOVERY_FAILED


def test_contract_replay_failure_returns_failed_result(tmp_path) -> None:
    service = _service(tmp_path)
    service.contract_replay_service.replay_all_for_job = lambda *args, **kwargs: {"status": "failed", "error_message": "contract failed"}

    result = service.replay_search("e2e-contract-fail", "search-e2e-fail", "xhs_dev_01", "eyeshadow", 20)

    assert result.status == "failed"
    assert result.error_code == XHS_E2E_REPLAY_CONTRACT_REPLAY_FAILED


def test_persistence_replay_failure_returns_failed_result(tmp_path) -> None:
    service = _service(tmp_path)
    service.persistence_replay_service.replay_all_for_job = lambda *args, **kwargs: {"status": "failed", "error_message": "persistence failed"}

    result = service.replay_search("e2e-persistence-fail", "search-e2e-fail", "xhs_dev_01", "eyeshadow", 20)

    assert result.status == "failed"
    assert result.error_code == XHS_E2E_REPLAY_PERSISTENCE_REPLAY_FAILED


def test_sensitive_input_is_blocked_without_writing_secret_value(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.replay_search("e2e-sensitive-fail", "search-e2e-fail", "xhs_dev_01", "Bearer abc", 20)
    input_text = Path(result.e2e_input_path).read_text(encoding="utf-8")

    assert result.status == "failed"
    assert result.error_code == XHS_E2E_REPLAY_SENSITIVE_PAYLOAD_DETECTED
    assert "Bearer abc" not in input_text
    assert service.scan_sensitive_artifacts({"token": "abc"})["passed"] is False
