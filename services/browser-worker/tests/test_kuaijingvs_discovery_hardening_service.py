import json

from app.services.kuaijingvs_discovery_hardening_service import KuaJingVSDiscoveryHardeningService
from app.utils.errors import (
    XHS_KJVS_DISCOVERY_SENSITIVE_VALUE_DETECTED,
    XHS_KJVS_DISCOVERY_SOURCE_NOT_FOUND,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path):
    return json.loads(open(path, encoding="utf-8").read())


def _service(tmp_path):
    return KuaJingVSDiscoveryHardeningService(worker_root=tmp_path)


def test_harden_discovery_evidence_reads_source_and_writes_outputs(tmp_path) -> None:
    source = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
    _write_json(
        source,
        {
            "status": "success",
            "shops": [
                {
                    "id": "123456",
                    "name": "小红书测试账号01",
                    "platform": "xhs",
                    "token": "redacted-by-hardening",
                    "cookie": "redacted-by-hardening",
                    "secret": "redacted-by-hardening",
                    "password": "redacted-by-hardening",
                    "authorization": "redacted-by-hardening",
                }
            ],
        },
    )

    result = _service(tmp_path).harden_discovery_evidence()
    hardened = _load(result.hardened_evidence_path)
    summary = _load(result.summary_path)

    assert result.status == "success"
    assert result.shop_count == 1
    assert result.evidence_hash.startswith("sha256:")
    assert hardened["shops"][0]["shop_id"] == "123456"
    assert hardened["shops"][0]["shop_name"] == "小红书测试账号01"
    assert hardened["shops"][0]["raw_keys"] == ["id", "name", "platform"]
    assert "token" not in hardened["shops"][0]
    assert "cookie" not in hardened["shops"][0]
    assert "secret" not in hardened["shops"][0]
    assert "password" not in hardened["shops"][0]
    assert "authorization" not in hardened["shops"][0]
    assert summary["ready_for_strict_account_binding"] is True


def test_source_discovery_missing_returns_source_not_found(tmp_path) -> None:
    result = _service(tmp_path).harden_discovery_evidence()

    assert result.status == "failed"
    assert result.error_code == XHS_KJVS_DISCOVERY_SOURCE_NOT_FOUND
    assert result.summary_path.endswith("hardened_discovery_summary.json")


def test_sensitive_values_fail_hardening(tmp_path) -> None:
    source = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
    for value in ("Bearer abc", "sessionid=abc", "access_token=abc"):
        _write_json(source, {"shops": [{"shop_id": "123", "shop_name": value}]})
        result = _service(tmp_path).harden_discovery_evidence()
        assert result.status == "failed"
        assert result.error_code == XHS_KJVS_DISCOVERY_SENSITIVE_VALUE_DETECTED


def test_validate_hardened_evidence_detects_sensitive_fields(tmp_path) -> None:
    service = _service(tmp_path)
    hardened = {
        "status": "success",
        "sanitization": {"sensitive_value_scan_passed": True},
        "forbidden": {"opened_shop": False},
        "shops": [{"shop_id": "123", "shop_name": "店铺", "token": "abc"}],
        "errors": [],
    }

    result = service.validate_hardened_evidence(hardened)

    assert result["valid"] is False
    assert result["errors"]
