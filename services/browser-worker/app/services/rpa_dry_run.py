import os
from pathlib import Path
from typing import Any

from app.schemas.search_job import SearchJob
from app.services.kuaijingvs_service import KuaJingVSService
from app.services.yingdao_service import YingdaoService
from app.utils.errors import (
    KJVS_CONFIG_ERROR,
    KJVS_PROFILE_NOT_FOUND,
    RPA_DRY_RUN_CONFIG_ERROR,
    RPA_DRY_RUN_EVIDENCE_DIR_ERROR,
    RPA_DRY_RUN_PROFILE_MAP_NOT_FOUND,
    YINGDAO_CONFIG_ERROR,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_RPA_PROVIDER_TYPES = {"yingdao_rpa", "kuaijingvs_yingdao_rpa"}


class RpaDryRunService:
    """Validate local RPA search configuration without external calls."""

    def __init__(
        self,
        kuaijingvs_service: KuaJingVSService | None = None,
        yingdao_service: YingdaoService | None = None,
        evidence_root: str | Path | None = None,
    ) -> None:
        """Create a dry-run service from local services and paths."""
        self.kuaijingvs_service = kuaijingvs_service or KuaJingVSService()
        self.yingdao_service = yingdao_service or YingdaoService()
        raw_evidence_root = evidence_root or os.getenv(
            "RPA_LOCAL_EVIDENCE_ROOT",
            ".local_evidence",
        )
        self.evidence_root = self._resolve_worker_path(raw_evidence_root)

    def check_search_job(self, job: SearchJob) -> dict:
        """Check a search job configuration without starting any RPA job."""
        checks: list[dict[str, Any]] = []
        resolved: dict[str, Any] = {}

        def add_check(
            name: str,
            status: str,
            message: str,
            value: Any | None = None,
        ) -> None:
            check = {"name": name, "status": status, "message": message}
            if value is not None:
                check["value"] = str(value)
            checks.append(check)

        def report(
            status: str,
            error_code: str | None = None,
            error_message: str | None = None,
        ) -> dict:
            return {
                "job_id": job.job_id,
                "provider_type": job.provider_type,
                "account_id": job.account_id,
                "keyword": job.keyword,
                "status": status,
                "checks": checks,
                "resolved": resolved,
                "error_code": error_code,
                "error_message": error_message,
            }

        if job.provider_type not in SUPPORTED_RPA_PROVIDER_TYPES:
            message = f"Unsupported RPA provider_type: {job.provider_type}"
            add_check("provider_type_supported", "failed", message, job.provider_type)
            return report("failed", RPA_DRY_RUN_CONFIG_ERROR, message)
        add_check(
            "provider_type_supported",
            "success",
            "provider_type is supported for RPA dry-run.",
            job.provider_type,
        )

        for field_name in ("job_id", "account_id", "keyword"):
            value = getattr(job, field_name)
            if not str(value or "").strip():
                message = f"{field_name} is required."
                add_check(f"{field_name}_present", "failed", message)
                return report("failed", RPA_DRY_RUN_CONFIG_ERROR, message)
            add_check(f"{field_name}_present", "success", f"{field_name} is present.")

        if job.provider_type == "kuaijingvs_yingdao_rpa":
            profile_map_result = self._check_profile_map(add_check)
            if profile_map_result is not None:
                error_code, error_message = profile_map_result
                return report("failed", error_code, error_message)

            try:
                shop_id = self.kuaijingvs_service.resolve_shop_id(job.account_id)
            except WorkerError as exc:
                error_code = (
                    RPA_DRY_RUN_PROFILE_MAP_NOT_FOUND
                    if exc.error_code == KJVS_CONFIG_ERROR
                    else exc.error_code
                )
                add_check(
                    "account_resolved",
                    "failed",
                    exc.error_message,
                    job.account_id,
                )
                return report("failed", error_code, exc.error_message)

            resolved["shop_id"] = shop_id
            add_check("account_resolved", "success", "account_id resolved to shop_id.", shop_id)

        yingdao_result = self._check_yingdao_config(add_check)
        if yingdao_result is not None:
            error_code, error_message = yingdao_result
            return report("failed", error_code, error_message)

        evidence_dir_result = self._prepare_evidence_paths(job.job_id, add_check, resolved)
        if evidence_dir_result is not None:
            error_code, error_message = evidence_dir_result
            return report("failed", error_code, error_message)

        return report("success")

    def _check_profile_map(self, add_check: Any) -> tuple[str, str] | None:
        """Validate the local KuaJingVS profile map path."""
        raw_path = self.kuaijingvs_service.profile_map_path
        if not str(raw_path or "").strip():
            message = "KJVS_PROFILE_MAP_PATH is not configured."
            add_check("profile_map_configured", "failed", message)
            return RPA_DRY_RUN_PROFILE_MAP_NOT_FOUND, message
        add_check("profile_map_configured", "success", "KJVS_PROFILE_MAP_PATH is configured.", raw_path)

        profile_map_path = self._resolve_worker_path(raw_path)
        if not profile_map_path.exists():
            message = f"KJVS profile map not found: {profile_map_path}"
            add_check("profile_map_exists", "failed", message, profile_map_path)
            return RPA_DRY_RUN_PROFILE_MAP_NOT_FOUND, message
        add_check("profile_map_exists", "success", "KJVS profile map exists.", profile_map_path)

        self.kuaijingvs_service.profile_map_path = str(profile_map_path)
        return None

    def _check_yingdao_config(self, add_check: Any) -> tuple[str, str] | None:
        """Validate Yingdao local config needed before real integration."""
        if self._is_placeholder_or_empty(self.yingdao_service.account_name):
            message = "YINGDAO_ACCOUNT_NAME is not configured."
            add_check("yingdao_account_name_configured", "failed", message)
            return YINGDAO_CONFIG_ERROR, message
        add_check(
            "yingdao_account_name_configured",
            "success",
            "YINGDAO_ACCOUNT_NAME is configured.",
            self.yingdao_service.account_name,
        )

        if self._is_placeholder_or_empty(self.yingdao_service.robot_uuid):
            message = "YINGDAO_ROBOT_UUID is not configured."
            add_check("yingdao_robot_uuid_configured", "failed", message)
            return YINGDAO_CONFIG_ERROR, message
        add_check(
            "yingdao_robot_uuid_configured",
            "success",
            "YINGDAO_ROBOT_UUID is configured.",
            self.yingdao_service.robot_uuid,
        )

        if self._is_placeholder_or_empty(self.yingdao_service.api_base_url):
            message = "YINGDAO_API_BASE_URL is not configured."
            add_check("yingdao_api_base_url_configured", "failed", message)
            return RPA_DRY_RUN_CONFIG_ERROR, message
        add_check(
            "yingdao_api_base_url_configured",
            "success",
            "YINGDAO_API_BASE_URL is configured.",
            self.yingdao_service.api_base_url,
        )
        return None

    def _prepare_evidence_paths(
        self,
        job_id: str,
        add_check: Any,
        resolved: dict[str, Any],
    ) -> tuple[str, str] | None:
        """Create the local evidence directory and expected output paths."""
        evidence_output_dir = self.evidence_root / job_id
        try:
            evidence_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            message = f"Cannot create evidence output dir: {evidence_output_dir}"
            add_check("evidence_output_dir_ready", "failed", message, evidence_output_dir)
            return RPA_DRY_RUN_EVIDENCE_DIR_ERROR, f"{message}: {exc}"

        expected_evidence_json_path = evidence_output_dir / "search_evidence.json"
        expected_screenshot_path = evidence_output_dir / "xhs_search_smoke.png"
        resolved.update(
            {
                "evidence_output_dir": str(evidence_output_dir),
                "expected_evidence_json_path": str(expected_evidence_json_path),
                "expected_screenshot_path": str(expected_screenshot_path),
            }
        )
        add_check(
            "evidence_output_dir_ready",
            "success",
            "Evidence output directory is ready.",
            evidence_output_dir,
        )
        return None

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative dry-run paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return BROWSER_WORKER_ROOT / path

    def _is_placeholder_or_empty(self, value: str | None) -> bool:
        """Return whether config is empty or still set to a placeholder."""
        normalized = str(value or "").strip()
        return normalized == "" or normalized.lower() == "change_me"
