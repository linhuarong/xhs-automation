from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.main import app
from app.services.audit_log_service import AuditLogService
from app.services.external_readiness_service import ExternalReadinessService
from app.schemas import KuaJingVSDiscoveryResult


client = TestClient(app)


def test_external_readiness_api_structure_and_audit(tmp_path, monkeypatch) -> None:
    audit_path = tmp_path / ".local_logs" / "xhs_audit.jsonl"
    monkeypatch.setattr(
        workflows_api,
        "readiness_service",
        ExternalReadinessService(env={}, worker_root=tmp_path),
    )
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(audit_path))

    response = client.get("/api/workflows/xhs/external-readiness")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["safe_mode"] is True
    assert body["summary"]["total"] == 25
    assert "dependencies" in body
    assert audit_path.exists()
    assert "external_readiness_check" in audit_path.read_text(encoding="utf-8")


def test_external_readiness_api_does_not_expose_secret_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        workflows_api,
        "readiness_service",
        ExternalReadinessService(
            env={
                "FEISHU_APP_ID": "real_app_id",
                "FEISHU_APP_SECRET": "super-secret-value",
                "FEISHU_XHS_WORKFLOW_TABLE_ID": "table-1",
            },
            worker_root=tmp_path,
        ),
    )
    monkeypatch.setattr(
        workflows_api,
        "audit_log_service",
        AuditLogService(tmp_path / ".local_logs" / "xhs_audit.jsonl"),
    )

    response_text = client.get("/api/workflows/xhs/external-readiness").text

    assert "super-secret-value" not in response_text
    assert "real_app_id" not in response_text
    assert "app_secret_configured" in response_text


class DisabledDiscoveryService:
    class Adapter:
        def __init__(self):
            self.discover_called = False

        def is_live_readonly_enabled(self):
            return False

    def __init__(self):
        self.adapter = self.Adapter()

    def discover(self):
        raise AssertionError("discover should not be called when live readonly is disabled")


class EnabledDiscoveryService:
    class Adapter:
        def is_live_readonly_enabled(self):
            return True

    def __init__(self):
        self.adapter = self.Adapter()

    def discover(self):
        return KuaJingVSDiscoveryResult(
            status="success",
            mode="live_readonly",
            safe_mode=True,
            api_base_url_configured=True,
            live_readonly_enabled=True,
            shop_count=1,
            shops=[{"shop_id": "123", "shop_name": "店铺", "raw_keys": ["shop_id"]}],
            profile_map_valid=True,
            matched_account_count=1,
            unmatched_account_count=0,
            evidence_json_path=".local_evidence/kuaijingvs_discovery/discovery.json",
        )


def test_kuaijingvs_discovery_api_blocked_without_live_readonly(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflows_api, "kuaijingvs_discovery_service", DisabledDiscoveryService())
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.get("/api/workflows/xhs/kuaijingvs/discovery")

    body = response.json()
    assert response.status_code == 400
    assert body["status"] == "blocked"
    assert body["error_code"] == "XHS_EXTERNAL_LIVE_CHECK_DISABLED"


def test_kuaijingvs_discovery_api_success_with_mock_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflows_api, "kuaijingvs_discovery_service", EnabledDiscoveryService())
    monkeypatch.setattr(workflows_api, "audit_log_service", AuditLogService(tmp_path / "audit.jsonl"))

    response = client.get("/api/workflows/xhs/kuaijingvs/discovery")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["shop_count"] == 1
    assert body["profile_map_valid"] is True
