import json
import os
from pathlib import Path
from typing import Mapping

from app.schemas.xhs_external_readiness import (
    ExternalDependencyStatus,
    ExternalReadinessResult,
    ExternalReadinessSummary,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_VALUES = {"", "change_me", "changeme", "none", "null"}
ALLOWED_PROFILE_PROVIDER_TYPES = {
    "kuaijingvs_yingdao_rpa",
    "yingdao_rpa",
    "manual",
    "selenium_chrome_debug",
}


class ExternalReadinessService:
    """Safe, no-network external readiness checks before real integration."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create an external readiness service."""
        self.env = env
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT

    def check_all(self) -> ExternalReadinessResult:
        """Run all safe readiness checks."""
        dependencies = [
            self.check_kuaijingvs(),
            self.check_kuaijingvs_discovery_hardening(),
            self.check_yingdao(),
            self.check_yingdao_local_handoff(),
            self.check_yingdao_desktop_smoke(),
            self.check_yingdao_form_fill_simulator(),
            self.check_yingdao_local_html_sandbox(),
            self.check_yingdao_selector_mapping(),
            self.check_yingdao_actual_form_fill(),
            self.check_xhs_account_binding(),
            self.check_xhs_account_binding_strict_mode(),
            self.check_feishu(),
            self.check_postgres(),
            self.check_minio(),
            self.check_local_contract_replay(),
            self.check_n8n_contract(),
            self.check_openclaw_contract(),
            self.check_local_storage(),
        ]
        summary = self._summarize(dependencies)
        return ExternalReadinessResult(
            status="success" if summary.failed == 0 else "failed",
            safe_mode=self.safe_mode,
            environment=self._get("APP_ENV", "local") or "local",
            summary=summary,
            dependencies=dependencies,
            metadata={
                "readiness_mode": self.readiness_mode,
                "live_readonly_checks_enabled": self.live_readonly_checks_enabled,
                "live_write_actions_enabled": self.live_write_actions_enabled,
            },
        )

    def check_yingdao_selector_mapping(self) -> ExternalDependencyStatus:
        """Check local HTML selector mapping report contract without preparing mappings."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        queue_root = self._resolve_worker_path(queue_root_value)
        mapping_root = queue_root / "selector_mapping"
        script_names = [
            "scripts/xhs_yingdao_selector_mapping_prepare.ps1",
            "scripts/xhs_yingdao_selector_mapping_open_report.ps1",
            "scripts/xhs_yingdao_selector_mapping_verify.ps1",
            "scripts/xhs_yingdao_selector_mapping_mock_confirm.ps1",
            "scripts/xhs_yingdao_selector_mapping_runbook.txt",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        enabled = self._truthy(self._get("YINGDAO_SELECTOR_MAPPING_ENABLED", "true"))
        allow_mock_confirm = self._truthy(self._get("YINGDAO_SELECTOR_MAPPING_ALLOW_MOCK_CONFIRM", "true"))
        allow_external_url = self._truthy(self._get("YINGDAO_SELECTOR_MAPPING_ALLOW_EXTERNAL_URL", "false"))
        allow_xhs_url = self._truthy(self._get("YINGDAO_SELECTOR_MAPPING_ALLOW_XHS_URL", "false"))
        allow_real_actions = self._truthy(self._get("YINGDAO_SELECTOR_MAPPING_ALLOW_REAL_ACTIONS", "false"))
        real_api_disabled = not self._truthy(self._get("YINGDAO_ENABLE_REAL_API", "false"))
        mapping_parent = mapping_root if mapping_root.exists() else mapping_root.parent
        mapping_queue_writable = mapping_parent.exists() and os.access(mapping_parent, os.W_OK)
        checks = {
            "selector_mapping_queue_writable": mapping_queue_writable,
            "selector_mapping_scripts_available": scripts_available,
            "mock_confirm_available": allow_mock_confirm,
            "safe_mode": not allow_external_url and not allow_xhs_url and not allow_real_actions and real_api_disabled,
            "real_yingdao_api_disabled": real_api_disabled,
            "external_url_forbidden": not allow_external_url,
            "xhs_url_forbidden": not allow_xhs_url,
            "real_publish_forbidden": not allow_real_actions,
        }
        if not enabled:
            status = "disabled"
            message = "Yingdao selector mapping report is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "Yingdao local HTML selector mapping report contract is ready"
        else:
            status = "missing_config"
            message = "Yingdao selector mapping scripts, local queue, or safety flags are incomplete"
        return ExternalDependencyStatus(
            name="yingdao_selector_mapping",
            mode="local_html_selector_mapping_report",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_yingdao_actual_form_fill(self) -> ExternalDependencyStatus:
        """Check actual local HTML form-fill smoke contract without preparing runs."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        queue_root = self._resolve_worker_path(queue_root_value)
        actual_root = queue_root / "actual_form_fill"
        script_names = [
            "scripts/xhs_yingdao_actual_form_fill_prepare.ps1",
            "scripts/xhs_yingdao_actual_form_fill_open.ps1",
            "scripts/xhs_yingdao_actual_form_fill_verify.ps1",
            "scripts/xhs_yingdao_actual_form_fill_mock_write.ps1",
            "scripts/xhs_yingdao_actual_form_fill_runbook.txt",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        enabled = self._truthy(self._get("YINGDAO_ACTUAL_FORM_FILL_ENABLED", "true"))
        allow_open_local_html = self._truthy(self._get("YINGDAO_ACTUAL_FORM_FILL_ALLOW_OPEN_LOCAL_HTML", "true"))
        allow_mock_write = self._truthy(self._get("YINGDAO_ACTUAL_FORM_FILL_ALLOW_MOCK_WRITE", "true"))
        allow_external_url = self._truthy(self._get("YINGDAO_ACTUAL_FORM_FILL_ALLOW_EXTERNAL_URL", "false"))
        allow_xhs_url = self._truthy(self._get("YINGDAO_ACTUAL_FORM_FILL_ALLOW_XHS_URL", "false"))
        allow_real_actions = self._truthy(self._get("YINGDAO_ACTUAL_FORM_FILL_ALLOW_REAL_ACTIONS", "false"))
        real_api_disabled = not self._truthy(self._get("YINGDAO_ENABLE_REAL_API", "false"))
        actual_parent = actual_root if actual_root.exists() else actual_root.parent
        actual_form_fill_queue_writable = actual_parent.exists() and os.access(actual_parent, os.W_OK)
        checks = {
            "actual_form_fill_queue_writable": actual_form_fill_queue_writable,
            "actual_form_fill_scripts_available": scripts_available,
            "open_local_html_available": allow_open_local_html,
            "mock_write_available": allow_mock_write,
            "safe_mode": not allow_external_url and not allow_xhs_url and not allow_real_actions and real_api_disabled,
            "real_yingdao_api_disabled": real_api_disabled,
            "external_url_forbidden": not allow_external_url,
            "xhs_url_forbidden": not allow_xhs_url,
            "real_publish_forbidden": not allow_real_actions,
        }
        if not enabled:
            status = "disabled"
            message = "Yingdao actual local form-fill smoke is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "Yingdao actual local HTML form-fill smoke contract is ready"
        else:
            status = "missing_config"
            message = "Yingdao actual form-fill scripts, local queue, or safety flags are incomplete"
        return ExternalDependencyStatus(
            name="yingdao_actual_form_fill",
            mode="local_html_actual_form_fill_smoke",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_xhs_account_binding(self) -> ExternalDependencyStatus:
        """Check account binding contract without discovery, open-shop, or network."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        queue_root = self._resolve_worker_path(queue_root_value)
        binding_root = queue_root / "account_binding"
        profile_map_value = self._get(
            "XHS_ACCOUNT_BINDING_PROFILE_MAP_PATH",
            self._get("KJVS_PROFILE_MAP_PATH", ".config/kuaijingvs_profiles.json"),
        )
        profile_map_path = self._resolve_worker_path(profile_map_value)
        discovery_path = self._resolve_worker_path(self._get("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")) / "kuaijingvs_discovery" / "discovery.json"
        script_names = [
            "scripts/xhs_account_binding_prepare.ps1",
            "scripts/xhs_account_binding_verify.ps1",
            "scripts/xhs_account_binding_mock_confirm.ps1",
            "scripts/xhs_account_binding_runbook.txt",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        enabled = self._truthy(self._get("XHS_ACCOUNT_BINDING_ENABLED", "true"))
        allow_mock_confirm = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_MOCK_CONFIRM", "true"))
        require_discovery = self._truthy(self._get("XHS_ACCOUNT_BINDING_REQUIRE_DISCOVERY_EVIDENCE", "false"))
        allow_open_shop = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_KJVS_OPEN_SHOP", "false"))
        allow_xhs_url = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_XHS_URL", "false"))
        allow_real_actions = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_REAL_ACTIONS", "false"))
        valid, _, _ = self.validate_profile_map(profile_map_path) if profile_map_path.exists() else (False, 0, None)
        binding_parent = binding_root if binding_root.exists() else binding_root.parent
        binding_queue_writable = binding_parent.exists() and os.access(binding_parent, os.W_OK)
        checks = {
            "profile_map_path_configured": self._value_configured(profile_map_value),
            "profile_map_exists": profile_map_path.exists(),
            "profile_map_valid": valid,
            "discovery_evidence_exists": discovery_path.exists(),
            "discovery_evidence_required": require_discovery,
            "account_binding_queue_writable": binding_queue_writable,
            "account_binding_scripts_available": scripts_available,
            "mock_confirm_available": allow_mock_confirm,
            "safe_mode": not allow_open_shop and not allow_xhs_url and not allow_real_actions,
            "kuaijingvs_open_shop_forbidden": not allow_open_shop,
            "xhs_url_forbidden": not allow_xhs_url,
            "real_publish_forbidden": not allow_real_actions,
        }
        ready = (
            checks["profile_map_path_configured"]
            and checks["profile_map_exists"]
            and checks["profile_map_valid"]
            and (checks["discovery_evidence_exists"] or not require_discovery)
            and binding_queue_writable
            and scripts_available
            and allow_mock_confirm
            and checks["safe_mode"]
        )
        if not enabled:
            status = "disabled"
            message = "XHS account binding check is disabled"
        elif ready:
            status = "ready"
            message = "XHS account binding contract is ready"
        else:
            status = "missing_config"
            message = "XHS account binding profile map, discovery evidence, scripts, or safety flags are incomplete"
        return ExternalDependencyStatus(
            name="xhs_account_binding",
            mode="kuaijingvs_profile_to_local_yingdao_binding",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_kuaijingvs_discovery_hardening(self) -> ExternalDependencyStatus:
        """Check local discovery hardening readiness without hardening or live calls."""
        source_path = self._resolve_worker_path(
            self._get("KJVS_DISCOVERY_SOURCE_PATH", ".local_evidence/kuaijingvs_discovery/discovery.json")
        )
        hardened_path = self._resolve_worker_path(
            self._get("KJVS_DISCOVERY_HARDENED_PATH", ".local_evidence/kuaijingvs_discovery/hardened_discovery.json")
        )
        summary_path = self._resolve_worker_path(
            self._get("KJVS_DISCOVERY_HARDENED_SUMMARY_PATH", ".local_evidence/kuaijingvs_discovery/hardened_discovery_summary.json")
        )
        script_path = self.worker_root / "scripts/xhs_kjvs_discovery_harden.ps1"
        hardened_safe = self._read_hardened_discovery_safe(hardened_path)
        checks = {
            "source_discovery_exists": source_path.exists(),
            "hardened_discovery_exists": hardened_path.exists(),
            "hardened_summary_exists": summary_path.exists(),
            "sensitive_filter_available": True,
            "evidence_hash_available": bool(hardened_safe.get("evidence_hash")),
            "hardening_script_available": script_path.exists(),
            "safe_mode": True,
            "open_shop_forbidden": True,
            "xhs_url_forbidden": True,
        }
        enabled = self._truthy(self._get("KJVS_DISCOVERY_HARDENING_ENABLED", "true"))
        if not enabled:
            status = "disabled"
            message = "KuaJingVS discovery evidence hardening is disabled"
        elif checks["source_discovery_exists"] and checks["hardening_script_available"]:
            status = "ready" if hardened_safe.get("safe") else "missing_config"
            message = (
                "KuaJingVS hardened discovery evidence is ready"
                if hardened_safe.get("safe")
                else "KuaJingVS source discovery is present; hardened evidence has not been generated or is unsafe"
            )
        else:
            status = "missing_config"
            message = "KuaJingVS discovery source evidence or hardening script is missing"
        return ExternalDependencyStatus(
            name="kuaijingvs_discovery_hardening",
            mode="local_evidence_hardening",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_xhs_account_binding_strict_mode(self) -> ExternalDependencyStatus:
        """Check strict account binding readiness without running strict checks."""
        profile_map_value = self._get(
            "XHS_ACCOUNT_BINDING_PROFILE_MAP_PATH",
            self._get("KJVS_PROFILE_MAP_PATH", ".config/kuaijingvs_profiles.json"),
        )
        profile_map_path = self._resolve_worker_path(profile_map_value)
        hardened_path = self._resolve_worker_path(
            self._get("KJVS_DISCOVERY_HARDENED_PATH", ".local_evidence/kuaijingvs_discovery/hardened_discovery.json")
        )
        scripts = [
            self.worker_root / "scripts/xhs_account_binding_strict_check.ps1",
            self.worker_root / "scripts/xhs_account_binding_strict_runbook.txt",
        ]
        allow_open_shop = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_KJVS_OPEN_SHOP", "false"))
        allow_xhs_url = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_XHS_URL", "false"))
        allow_real_actions = self._truthy(self._get("XHS_ACCOUNT_BINDING_ALLOW_REAL_ACTIONS", "false"))
        hardened_safe = self._read_hardened_discovery_safe(hardened_path)
        checks = {
            "profile_map_exists": profile_map_path.exists(),
            "hardened_discovery_exists": hardened_path.exists(),
            "hardened_discovery_safe": bool(hardened_safe.get("safe")),
            "strict_mode_enabled": self._truthy(self._get("XHS_ACCOUNT_BINDING_STRICT_MODE_ENABLED", "true")),
            "strict_scripts_available": all(path.exists() for path in scripts),
            "open_shop_forbidden": not allow_open_shop,
            "xhs_url_forbidden": not allow_xhs_url,
            "real_publish_forbidden": not allow_real_actions,
        }
        if not checks["strict_mode_enabled"]:
            status = "disabled"
            message = "XHS account binding strict mode is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "XHS account binding strict mode is ready"
        else:
            status = "missing_config"
            message = "XHS account binding strict mode needs profile map, safe hardened discovery, scripts, and safety flags"
        return ExternalDependencyStatus(
            name="xhs_account_binding_strict_mode",
            mode="local_strict_binding_check",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_yingdao_local_html_sandbox(self) -> ExternalDependencyStatus:
        """Check local static HTML sandbox contract without preparing or opening pages."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        queue_root = self._resolve_worker_path(queue_root_value)
        sandbox_root = queue_root / "sandbox"
        script_names = [
            "scripts/xhs_yingdao_html_sandbox_prepare.ps1",
            "scripts/xhs_yingdao_html_sandbox_open.ps1",
            "scripts/xhs_yingdao_html_sandbox_verify.ps1",
            "scripts/xhs_yingdao_html_sandbox_mock_write.ps1",
            "scripts/xhs_yingdao_html_sandbox_runbook.txt",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        enabled = self._truthy(self._get("YINGDAO_HTML_SANDBOX_ENABLED", "true"))
        allow_mock_write = self._truthy(self._get("YINGDAO_HTML_SANDBOX_ALLOW_MOCK_WRITE", "true"))
        allow_external_url = self._truthy(self._get("YINGDAO_HTML_SANDBOX_ALLOW_EXTERNAL_URL", "false"))
        allow_xhs_url = self._truthy(self._get("YINGDAO_HTML_SANDBOX_ALLOW_XHS_URL", "false"))
        allow_real_actions = self._truthy(self._get("YINGDAO_HTML_SANDBOX_ALLOW_REAL_ACTIONS", "false"))
        real_api_disabled = not self._truthy(self._get("YINGDAO_ENABLE_REAL_API", "false"))
        sandbox_parent = sandbox_root if sandbox_root.exists() else sandbox_root.parent
        sandbox_queue_writable = sandbox_parent.exists() and os.access(sandbox_parent, os.W_OK)
        checks = {
            "sandbox_queue_writable": sandbox_queue_writable,
            "html_sandbox_scripts_available": scripts_available,
            "mock_write_available": allow_mock_write,
            "safe_mode": not allow_external_url and not allow_xhs_url and not allow_real_actions and real_api_disabled,
            "real_yingdao_api_disabled": real_api_disabled,
            "external_url_forbidden": not allow_external_url,
            "xhs_url_forbidden": not allow_xhs_url,
            "real_actions_disabled": not allow_real_actions,
        }
        if not enabled:
            status = "disabled"
            message = "Yingdao local HTML sandbox is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "Yingdao local static HTML sandbox contract is ready"
        else:
            status = "missing_config"
            message = "Yingdao local HTML sandbox scripts, local queue, or safety flags are incomplete"
        return ExternalDependencyStatus(
            name="yingdao_local_html_sandbox",
            mode="local_static_html_sandbox",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_yingdao_form_fill_simulator(self) -> ExternalDependencyStatus:
        """Check browserless form-fill simulator contract without preparing packages."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        queue_root = self._resolve_worker_path(queue_root_value)
        simulator_root = queue_root / "simulator"
        script_names = [
            "scripts/xhs_yingdao_form_sim_prepare.ps1",
            "scripts/xhs_yingdao_form_sim_verify.ps1",
            "scripts/xhs_yingdao_form_sim_mock_write.ps1",
            "scripts/xhs_yingdao_form_sim_runbook.txt",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        enabled = self._truthy(self._get("YINGDAO_FORM_SIMULATOR_ENABLED", "true"))
        allow_mock_write = self._truthy(self._get("YINGDAO_FORM_SIMULATOR_ALLOW_MOCK_WRITE", "true"))
        open_browser = self._truthy(self._get("YINGDAO_FORM_SIMULATOR_OPEN_BROWSER", "false"))
        open_xhs = self._truthy(self._get("YINGDAO_FORM_SIMULATOR_OPEN_XHS", "false"))
        allow_real_actions = self._truthy(self._get("YINGDAO_FORM_SIMULATOR_ALLOW_REAL_ACTIONS", "false"))
        real_api_disabled = not self._truthy(self._get("YINGDAO_ENABLE_REAL_API", "false"))
        simulator_parent = simulator_root if simulator_root.exists() else simulator_root.parent
        simulator_queue_writable = simulator_parent.exists() and os.access(simulator_parent, os.W_OK)
        checks = {
            "simulator_queue_writable": simulator_queue_writable,
            "form_simulator_scripts_available": scripts_available,
            "mock_write_available": allow_mock_write,
            "safe_mode": not open_browser and not open_xhs and not allow_real_actions and real_api_disabled,
            "real_yingdao_api_disabled": real_api_disabled,
            "browser_open_disabled": not open_browser,
            "xhs_open_disabled": not open_xhs,
            "real_actions_disabled": not allow_real_actions,
        }
        if not enabled:
            status = "disabled"
            message = "Yingdao browserless form-fill simulator is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "Yingdao browserless form-fill simulator contract is ready"
        else:
            status = "missing_config"
            message = "Yingdao form-fill simulator scripts, local queue, or safety flags are incomplete"
        return ExternalDependencyStatus(
            name="yingdao_form_fill_simulator",
            mode="browserless_local_json_simulator",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_yingdao_desktop_smoke(self) -> ExternalDependencyStatus:
        """Check manual Yingdao desktop smoke contract without preparing jobs."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        queue_root = self._resolve_worker_path(queue_root_value)
        smoke_root = queue_root / "smoke"
        script_names = [
            "scripts/xhs_yingdao_desktop_smoke_prepare.ps1",
            "scripts/xhs_yingdao_desktop_smoke_verify.ps1",
            "scripts/xhs_yingdao_desktop_smoke_mock_write.ps1",
            "scripts/xhs_yingdao_desktop_smoke_runbook.txt",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        enabled = self._truthy(self._get("YINGDAO_DESKTOP_SMOKE_ENABLED", "true"))
        allow_mock_write = self._truthy(self._get("YINGDAO_DESKTOP_SMOKE_ALLOW_MOCK_WRITE", "true"))
        open_browser = self._truthy(self._get("YINGDAO_DESKTOP_SMOKE_OPEN_BROWSER", "false"))
        open_xhs = self._truthy(self._get("YINGDAO_DESKTOP_SMOKE_OPEN_XHS", "false"))
        real_api_disabled = not self._truthy(self._get("YINGDAO_ENABLE_REAL_API", "false"))
        smoke_parent = smoke_root if smoke_root.exists() else smoke_root.parent
        smoke_queue_writable = smoke_parent.exists() and os.access(smoke_parent, os.W_OK)
        local_handoff = self.check_yingdao_local_handoff()
        checks = {
            "local_handoff_ready": local_handoff.status == "ready",
            "smoke_queue_writable": smoke_queue_writable,
            "desktop_smoke_scripts_available": scripts_available,
            "mock_write_available": allow_mock_write,
            "safe_mode": not open_browser and not open_xhs and real_api_disabled,
            "real_yingdao_api_disabled": real_api_disabled,
            "browser_open_disabled": not open_browser,
            "xhs_open_disabled": not open_xhs,
        }
        if not enabled:
            status = "disabled"
            message = "Yingdao desktop smoke is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "Yingdao desktop manual smoke contract is ready"
        else:
            status = "missing_config"
            message = "Yingdao desktop smoke scripts, local queue, or safety flags are incomplete"
        return ExternalDependencyStatus(
            name="yingdao_desktop_smoke",
            mode="manual_local_file_smoke",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_yingdao_local_handoff(self) -> ExternalDependencyStatus:
        """Check the local Yingdao file handoff contract without generating jobs."""
        queue_root_value = self._get("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        search_active_value = self._get(
            "YINGDAO_SEARCH_ACTIVE_JOB_PATH",
            ".local_rpa_queue/yingdao/search/_active_job.json",
        )
        publish_active_value = self._get(
            "YINGDAO_PUBLISH_ACTIVE_JOB_PATH",
            ".local_rpa_queue/yingdao/publish/_active_publish_job.json",
        )
        queue_root = self._resolve_worker_path(queue_root_value)
        script_names = [
            "scripts/xhs_yingdao_prepare_search_handoff.ps1",
            "scripts/xhs_yingdao_prepare_publish_handoff.ps1",
            "scripts/xhs_yingdao_check_active_job.ps1",
            "scripts/xhs_yingdao_mock_evidence.ps1",
        ]
        scripts_available = all((self.worker_root / name).exists() for name in script_names)
        provider_registered = self._yingdao_local_provider_registered()
        enabled = self._truthy(self._get("YINGDAO_LOCAL_HANDOFF_ENABLED", "true"))
        safe_mode = self._truthy(self._get("YINGDAO_LOCAL_HANDOFF_SAFE_MODE", "true"))
        queue_parent = queue_root if queue_root.exists() else queue_root.parent
        queue_root_writable = queue_parent.exists() and os.access(queue_parent, os.W_OK)
        checks = {
            "enabled": enabled,
            "queue_root_exists": queue_root.exists(),
            "queue_root_writable": queue_root_writable,
            "search_active_job_path_configured": self._value_configured(search_active_value),
            "publish_active_job_path_configured": self._value_configured(publish_active_value),
            "scripts_available": scripts_available,
            "provider_registered": provider_registered,
            "safe_mode": safe_mode,
            "real_api_enabled": self._truthy(self._get("YINGDAO_ENABLE_REAL_API", "false")),
        }
        ready = enabled and queue_root_writable and checks["search_active_job_path_configured"] and checks[
            "publish_active_job_path_configured"
        ] and scripts_available and provider_registered and safe_mode
        if not enabled:
            status = "disabled"
            message = "Yingdao local handoff is disabled"
        elif ready:
            status = "ready"
            message = "Yingdao local file handoff contract is ready"
        else:
            status = "missing_config"
            message = "Yingdao local handoff paths, scripts, or provider registration are incomplete"
        return ExternalDependencyStatus(
            name="yingdao_local_handoff",
            mode="local_file_contract",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_kuaijingvs(self) -> ExternalDependencyStatus:
        """Check KuaJingVS config and profile map shape without opening shops."""
        profile_map_path_value = self._get("KJVS_PROFILE_MAP_PATH")
        profile_path = self._resolve_worker_path(profile_map_path_value) if profile_map_path_value else None
        discovery_evidence_path = self._resolve_worker_path(
            self._get("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")
        ) / "kuaijingvs_discovery" / "discovery.json"
        checks: dict[str, bool | str | int | None] = {
            "live_readonly_enabled": self.live_readonly_checks_enabled,
            "api_base_url_configured": self._configured("KJVS_API_BASE_URL"),
            "api_id_configured": self._configured("KJVS_API_ID"),
            "api_secret_configured": self._configured("KJVS_API_SECRET"),
            "profile_map_path_configured": self._configured("KJVS_PROFILE_MAP_PATH"),
            "profile_map_exists": bool(profile_path and profile_path.exists()),
            "profile_map_valid": False,
            "profile_count": 0,
            "discovery_api_available": discovery_evidence_path.exists(),
            "last_discovery_evidence_path": str(discovery_evidence_path) if discovery_evidence_path.exists() else None,
        }
        status = "missing_config"
        message = "KJVS_API_BASE_URL or KJVS_PROFILE_MAP_PATH is not configured"
        if profile_path and profile_path.exists():
            valid, profile_count, error_message = self.validate_profile_map(profile_path)
            checks["profile_map_valid"] = valid
            checks["profile_count"] = profile_count
            if valid and checks["api_base_url_configured"]:
                status = "ready"
                message = "KuaJingVS config is present for dry-run readiness"
            else:
                status = "failed" if error_message else "missing_config"
                message = error_message or message
        return ExternalDependencyStatus(
            name="kuaijingvs",
            mode="live_readonly" if self.live_readonly_checks_enabled else self.readiness_mode,
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_yingdao(self) -> ExternalDependencyStatus:
        """Check Yingdao config placeholders without starting jobs."""
        checks = {
            "api_base_url_configured": self._configured("YINGDAO_API_BASE_URL"),
            "access_key_id_configured": self._configured("YINGDAO_ACCESS_KEY_ID"),
            "access_key_secret_configured": self._configured("YINGDAO_ACCESS_KEY_SECRET"),
            "account_name_configured": self._configured("YINGDAO_ACCOUNT_NAME"),
            "robot_uuid_configured": self._configured("YINGDAO_ROBOT_UUID"),
        }
        ready = all(checks.values())
        return ExternalDependencyStatus(
            name="yingdao",
            mode=self.readiness_mode,
            status="ready" if ready else "missing_config",
            required=False,
            message="Yingdao config is present for dry-run readiness"
            if ready
            else "YINGDAO_ACCOUNT_NAME or YINGDAO_ROBOT_UUID is not configured",
            checks=checks,
        )

    def check_feishu(self) -> ExternalDependencyStatus:
        """Check Feishu config placeholders only."""
        checks = {
            "app_id_configured": self._configured("FEISHU_APP_ID"),
            "app_secret_configured": self._configured("FEISHU_APP_SECRET"),
            "workflow_table_id_configured": self._configured("FEISHU_XHS_WORKFLOW_TABLE_ID"),
        }
        ready = all(checks.values())
        return ExternalDependencyStatus(
            name="feishu",
            mode="mock" if not ready else self.readiness_mode,
            status="mock_ready" if not ready else "ready",
            required=False,
            message="Feishu adapter is available in mock mode" if not ready else "Feishu config placeholders are present",
            checks=checks,
        )

    def check_postgres(self) -> ExternalDependencyStatus:
        """Check PostgreSQL DSN placeholder only."""
        configured = self._configured("POSTGRES_DSN")
        return ExternalDependencyStatus(
            name="postgres",
            mode="mock" if not configured else self.readiness_mode,
            status="mock_ready" if not configured else "ready",
            required=False,
            message="PostgreSQL repository is available in mock mode"
            if not configured
            else "PostgreSQL DSN is configured for future dry-run readiness",
            checks={"dsn_configured": configured},
        )

    def check_minio(self) -> ExternalDependencyStatus:
        """Check MinIO config placeholders only."""
        checks = {
            "endpoint_configured": self._configured("MINIO_ENDPOINT"),
            "access_key_configured": self._configured("MINIO_ACCESS_KEY"),
            "secret_key_configured": self._configured("MINIO_SECRET_KEY"),
            "bucket_configured": self._configured("MINIO_BUCKET"),
        }
        ready = all(checks.values())
        return ExternalDependencyStatus(
            name="minio",
            mode="mock" if not ready else self.readiness_mode,
            status="mock_ready" if not ready else "ready",
            required=False,
            message="MinIO storage adapter is available in local mock mode"
            if not ready
            else "MinIO config placeholders are present",
            checks=checks,
        )

    def check_n8n_contract(self) -> ExternalDependencyStatus:
        """Check local n8n webhook contract availability."""
        return ExternalDependencyStatus(
            name="n8n",
            mode="mock",
            status="mock_ready",
            required=False,
            message="n8n webhook contract is available in mock mode",
            checks={
                "base_url_configured": self._configured("N8N_BASE_URL"),
                "search_path_configured": self._configured("N8N_XHS_SEARCH_WEBHOOK_PATH"),
                "publish_path_configured": self._configured("N8N_XHS_PUBLISH_WEBHOOK_PATH"),
                "webhook_search_route": True,
                "webhook_publish_route": True,
            },
        )

    def check_openclaw_contract(self) -> ExternalDependencyStatus:
        """Check local OpenClaw job-status contract availability."""
        return ExternalDependencyStatus(
            name="openclaw",
            mode="mock",
            status="mock_ready",
            required=False,
            message="OpenClaw job-status contract is available in mock mode",
            checks={
                "base_url_configured": self._configured("OPENCLAW_BASE_URL"),
                "job_status_path_configured": self._configured("OPENCLAW_XHS_JOB_STATUS_PATH"),
                "job_status_route": True,
            },
        )

    def check_local_contract_replay(self) -> ExternalDependencyStatus:
        """Check local n8n/OpenClaw contract replay readiness without replaying."""
        replay_root = self._resolve_worker_path(self._get("XHS_LOCAL_CONTRACT_REPLAY_ROOT", ".local_rpa_queue/replay"))
        scripts = [
            self.worker_root / "scripts/xhs_contract_replay_n8n_search.ps1",
            self.worker_root / "scripts/xhs_contract_replay_n8n_publish.ps1",
            self.worker_root / "scripts/xhs_contract_replay_openclaw_status.ps1",
            self.worker_root / "scripts/xhs_contract_replay_all.ps1",
            self.worker_root / "scripts/xhs_contract_replay_runbook.txt",
        ]
        replay_parent = replay_root if replay_root.exists() else replay_root.parent
        allow_external_n8n = self._truthy(self._get("XHS_LOCAL_CONTRACT_REPLAY_ALLOW_EXTERNAL_N8N", "false"))
        allow_external_openclaw = self._truthy(self._get("XHS_LOCAL_CONTRACT_REPLAY_ALLOW_EXTERNAL_OPENCLAW", "false"))
        hardened_path = self._resolve_worker_path(
            self._get("KJVS_DISCOVERY_HARDENED_PATH", ".local_evidence/kuaijingvs_discovery/hardened_discovery.json")
        )
        hardened_safe = self._read_hardened_discovery_safe(hardened_path)
        checks = {
            "n8n_mock_search_route_available": True,
            "n8n_mock_publish_route_available": True,
            "openclaw_mock_job_status_route_available": True,
            "replay_queue_writable": replay_parent.exists() and os.access(replay_parent, os.W_OK),
            "replay_scripts_available": all(path.exists() for path in scripts),
            "strict_binding_available": self._truthy(self._get("XHS_ACCOUNT_BINDING_STRICT_MODE_ENABLED", "true")),
            "hardened_discovery_available": bool(hardened_safe.get("safe")),
            "sensitive_scan_available": True,
            "external_n8n_call_forbidden": not allow_external_n8n,
            "external_openclaw_call_forbidden": not allow_external_openclaw,
            "safe_mode": not allow_external_n8n and not allow_external_openclaw and not self.live_write_actions_enabled,
        }
        enabled = self._truthy(self._get("XHS_LOCAL_CONTRACT_REPLAY_ENABLED", "true"))
        if not enabled:
            status = "disabled"
            message = "Local n8n/OpenClaw contract replay is disabled"
        elif all(checks.values()):
            status = "ready"
            message = "Local n8n/OpenClaw contract replay is ready"
        else:
            status = "missing_config"
            message = "Local contract replay needs scripts, writable queue, hardened discovery, and safe external-call flags"
        return ExternalDependencyStatus(
            name="local_contract_replay",
            mode="local_n8n_openclaw_replay",
            status=status,
            required=False,
            message=message,
            checks=checks,
        )

    def check_local_storage(self) -> ExternalDependencyStatus:
        """Check local queue/evidence/archive path configuration only."""
        queue_root = self._get("RPA_LOCAL_QUEUE_ROOT", ".local_rpa_jobs")
        evidence_root = self._get("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")
        archive_root = self._get("XHS_LOCAL_ARCHIVE_ROOT", ".local_archive")
        return ExternalDependencyStatus(
            name="local_storage",
            mode="dry_run",
            status="ready",
            required=True,
            message="Local queue, evidence, archive, and audit paths are configured",
            checks={
                "queue_root_configured": bool(queue_root),
                "evidence_root_configured": bool(evidence_root),
                "archive_root_configured": bool(archive_root),
                "queue_root": queue_root,
                "evidence_root": evidence_root,
                "archive_root": archive_root,
            },
        )

    def validate_profile_map(self, path: str | Path) -> tuple[bool, int, str | None]:
        """Validate KuaJingVS profile map JSON shape without calling KuaJingVS."""
        profile_path = Path(path)
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False, 0, f"profile map not found: {profile_path}"
        except json.JSONDecodeError as exc:
            return False, 0, f"profile map JSON invalid: {profile_path}: {exc}"
        if not isinstance(payload, dict):
            return False, 0, "profile map must be a JSON object"
        for account_id, profile in payload.items():
            if not isinstance(profile, dict):
                return False, len(payload), f"profile map entry must be an object: {account_id}"
            missing = [field for field in ("shop_id", "shop_name", "provider_type") if not profile.get(field)]
            if missing:
                return False, len(payload), f"profile map entry {account_id} missing fields: {', '.join(missing)}"
            provider_type = str(profile.get("provider_type"))
            if provider_type not in ALLOWED_PROFILE_PROVIDER_TYPES:
                return False, len(payload), f"profile map entry {account_id} has unsupported provider_type: {provider_type}"
        return True, len(payload), None

    @property
    def readiness_mode(self) -> str:
        """Return external readiness mode."""
        return self._get("XHS_EXTERNAL_READINESS_MODE", "dry_run") or "dry_run"

    @property
    def live_readonly_checks_enabled(self) -> bool:
        """Return whether live readonly checks are explicitly enabled."""
        return self._truthy(self._get("XHS_ALLOW_LIVE_READONLY_CHECKS", "false"))

    @property
    def live_write_actions_enabled(self) -> bool:
        """Return whether live write actions are explicitly enabled."""
        return self._truthy(self._get("XHS_ALLOW_LIVE_WRITE_ACTIONS", "false"))

    @property
    def safe_mode(self) -> bool:
        """Readiness is safe unless live writes are explicitly enabled."""
        return not self.live_write_actions_enabled

    def _summarize(self, dependencies: list[ExternalDependencyStatus]) -> ExternalReadinessSummary:
        """Count dependency statuses."""
        counts = {
            "total": len(dependencies),
            "ready": 0,
            "mock_ready": 0,
            "disabled": 0,
            "missing_config": 0,
            "failed": 0,
        }
        for dependency in dependencies:
            if dependency.status in counts:
                counts[dependency.status] += 1
        return ExternalReadinessSummary(**counts)

    def _configured(self, name: str) -> bool:
        """Return whether an env config value is present and not a placeholder."""
        return self._value_configured(self._get(name))

    def _value_configured(self, value: str | None) -> bool:
        """Return whether a value is present and not a placeholder."""
        normalized = str(value or "").strip()
        return normalized.lower() not in PLACEHOLDER_VALUES

    def _get(self, name: str, default: str | None = None) -> str | None:
        """Read from injected env mapping or process environment."""
        source = self.env if self.env is not None else os.environ
        value = source.get(name, default)
        return str(value).strip() if value is not None else None

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _truthy(self, value: str | None) -> bool:
        """Parse boolean-like environment values."""
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _read_hardened_discovery_safe(self, path: Path) -> dict[str, str | bool | None]:
        """Read only safe hardened discovery status for readiness."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"safe": False, "evidence_hash": None}
        safe = (
            isinstance(payload, dict)
            and payload.get("status") == "success"
            and bool((payload.get("sanitization") or {}).get("sensitive_value_scan_passed"))
            and bool(payload.get("evidence_hash"))
            and not any((payload.get("forbidden") or {}).values())
            and not (payload.get("errors") or [])
        )
        return {"safe": safe, "evidence_hash": payload.get("evidence_hash") if isinstance(payload, dict) else None}

    def _yingdao_local_provider_registered(self) -> bool:
        """Return whether the local handoff provider is registered."""
        try:
            from app.providers import get_provider

            provider = get_provider("yingdao_local_file_trigger")
            return getattr(provider, "provider_type", None) == "yingdao_local_file_trigger"
        except Exception:
            return False
