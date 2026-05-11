import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    XhsAccountBindingConfirmation,
    XhsAccountBindingConfirmationRuntime,
    XhsAccountBindingContext,
    XhsAccountBindingInput,
    XhsAccountBindingPrepareResult,
    XhsAccountBindingStrictInput,
    XhsAccountBindingStrictResult,
    XhsAccountBindingStrictRules,
    XhsAccountBindingStrictSummary,
    XhsAccountBindingSummary,
    XhsAccountBindingVerifyResult,
    XhsDiscoveryMatchedShop,
    XhsMappedProfile,
)
from app.services.external_readiness_service import ALLOWED_PROFILE_PROVIDER_TYPES
from app.services.yingdao_actual_form_fill_smoke_service import YingdaoActualFormFillSmokeService
from app.utils.errors import (
    XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND,
    XHS_ACCOUNT_BINDING_CONFIRMATION_INVALID,
    XHS_ACCOUNT_BINDING_CONFIRMATION_NOT_FOUND,
    XHS_ACCOUNT_BINDING_DISCOVERY_MISSING,
    XHS_ACCOUNT_BINDING_ERROR,
    XHS_ACCOUNT_BINDING_FORBIDDEN_ACTION,
    XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID,
    XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING,
    XHS_ACCOUNT_BINDING_REAL_ACTION_FORBIDDEN,
    XHS_ACCOUNT_BINDING_SHOP_UNMATCHED,
    XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_MISSING,
    XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_UNSAFE,
    XHS_ACCOUNT_BINDING_STRICT_ERROR,
    XHS_ACCOUNT_BINDING_STRICT_PROVIDER_TYPE_INVALID,
    XHS_ACCOUNT_BINDING_STRICT_SHOP_NAME_MISMATCH,
    XHS_ACCOUNT_BINDING_STRICT_SHOP_UNMATCHED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class XhsAccountBindingService:
    """Bind KuaJingVS profile map entries to local Yingdao form-fill inputs."""

    def __init__(
        self,
        actual_form_fill_service: YingdaoActualFormFillSmokeService | None = None,
        profile_map_path: str | Path | None = None,
        discovery_evidence_path: str | Path | None = None,
        queue_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create account binding service without calling network or opening shops."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.actual_form_fill_service = actual_form_fill_service or YingdaoActualFormFillSmokeService(
            queue_root=queue_root,
            worker_root=self.worker_root,
        )
        self.queue_root = self.actual_form_fill_service.queue_root
        self.profile_map_path = self._resolve_worker_path(
            profile_map_path
            or os.getenv("XHS_ACCOUNT_BINDING_PROFILE_MAP_PATH")
            or os.getenv("KJVS_PROFILE_MAP_PATH", ".config/kuaijingvs_profiles.json")
        )
        self.discovery_evidence_path = self._resolve_worker_path(
            discovery_evidence_path
            or (self.worker_root / os.getenv("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence") / "kuaijingvs_discovery" / "discovery.json")
        )
        self.hardened_discovery_path = self._resolve_worker_path(
            os.getenv("KJVS_DISCOVERY_HARDENED_PATH", ".local_evidence/kuaijingvs_discovery/hardened_discovery.json")
        )

    def prepare_search_account_binding(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> XhsAccountBindingPrepareResult:
        """Prepare search account binding package."""
        actual = self.actual_form_fill_service.prepare_search_actual_fill(job_id, account_id, keyword, limit)
        return self._prepare_binding("xhs_search", job_id, account_id, actual.actual_form_fill_input_path)

    def prepare_publish_account_binding(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> XhsAccountBindingPrepareResult:
        """Prepare publish account binding package."""
        actual = self.actual_form_fill_service.prepare_publish_actual_fill(
            job_id,
            account_id,
            title,
            body,
            tags,
            image_paths,
            publish_mode,
        )
        return self._prepare_binding("xhs_publish", job_id, account_id, actual.actual_form_fill_input_path)

    def prepare_search_strict_binding_check(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> XhsAccountBindingStrictResult:
        """Run strict search account binding check using hardened discovery only."""
        return self._prepare_strict_binding("xhs_search", job_id, account_id)

    def prepare_publish_strict_binding_check(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> XhsAccountBindingStrictResult:
        """Run strict publish account binding check using hardened discovery only."""
        return self._prepare_strict_binding("xhs_publish", job_id, account_id)

    def load_profile_map(self, profile_map_path: str | Path) -> dict[str, Any]:
        """Load local profile map JSON."""
        path = self._resolve_worker_path(profile_map_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING, f"profile map not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID, f"profile map JSON invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID, "profile map must be a JSON object")
        for account_id, profile in payload.items():
            if not isinstance(profile, dict):
                raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID, f"profile map entry must be object: {account_id}")
            missing = [field for field in ("shop_id", "shop_name", "provider_type") if not profile.get(field)]
            if missing:
                raise WorkerError(
                    XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID,
                    f"profile map entry {account_id} missing fields: {', '.join(missing)}",
                )
            if str(profile.get("provider_type")) not in ALLOWED_PROFILE_PROVIDER_TYPES:
                raise WorkerError(
                    XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID,
                    f"profile map entry {account_id} has unsupported provider_type: {profile.get('provider_type')}",
                )
        return payload

    def load_kuaijingvs_discovery_evidence(self, evidence_path: str | Path) -> dict[str, Any]:
        """Load local KuaJingVS discovery evidence JSON."""
        path = self._resolve_worker_path(evidence_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_DISCOVERY_MISSING, f"discovery evidence not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_DISCOVERY_MISSING, f"discovery evidence JSON invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(XHS_ACCOUNT_BINDING_DISCOVERY_MISSING, "discovery evidence must be a JSON object")
        return payload

    def resolve_account_profile(self, account_id: str, profile_map: dict[str, Any]) -> dict[str, Any]:
        """Resolve one account profile from profile map."""
        profile = profile_map.get(account_id)
        if not isinstance(profile, dict):
            raise WorkerError(XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND, f"account_id not found in profile map: {account_id}")
        return {"account_id": account_id, **profile}

    def match_shop_from_discovery(self, shop_id: str, discovery: dict[str, Any]) -> dict[str, Any]:
        """Match shop_id from local discovery evidence."""
        shops = discovery.get("shops") or []
        for shop in shops:
            if str(shop.get("shop_id")) == str(shop_id):
                return dict(shop)
        raise WorkerError(XHS_ACCOUNT_BINDING_SHOP_UNMATCHED, f"shop_id not found in discovery evidence: {shop_id}")

    def build_account_binding_context(
        self,
        job_type: str,
        job_id: str,
        account_id: str,
        profile: dict[str, Any] | None,
        discovery: dict[str, Any] | None,
        profile_error: WorkerError | None = None,
        discovery_error: WorkerError | None = None,
    ) -> dict[str, Any]:
        """Build account binding context without any live action."""
        normalized = self._normalize_job_type(job_type)
        warnings: list[str] = []
        errors: list[str] = []
        status = "matched"
        mapped_profile = None
        matched_shop = None
        profile_valid = profile_error is None and profile is not None
        account_found = profile_valid
        discovery_exists = discovery_error is None and discovery is not None
        shop_found = False

        if profile_error is not None:
            if profile_error.error_code == XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING:
                status = "profile_map_missing"
            elif profile_error.error_code == XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND:
                status = "account_not_found"
            else:
                status = "profile_map_invalid"
            errors.append(profile_error.error_message)
        elif profile is not None:
            mapped_profile = XhsMappedProfile(
                account_id=account_id,
                shop_id=str(profile.get("shop_id")),
                shop_name=str(profile.get("shop_name")),
                provider_type=str(profile.get("provider_type", "kuaijingvs_yingdao_rpa")),
            )
        else:
            status = "account_not_found"
            errors.append(f"account_id not found in profile map: {account_id}")

        if discovery_error is not None:
            if status == "matched":
                status = "discovery_missing"
            warnings.append(discovery_error.error_message)
        elif mapped_profile is not None and discovery is not None:
            try:
                shop = self.match_shop_from_discovery(str(mapped_profile.shop_id), discovery)
                shop_found = True
                discovered_name = str(shop.get("shop_name") or "")
                profile_name = str(mapped_profile.shop_name or "")
                name_matches = bool(discovered_name and profile_name and discovered_name == profile_name)
                if discovered_name and profile_name and not name_matches:
                    status = "warning_name_mismatch"
                    warnings.append("shop_name differs between profile map and discovery evidence")
                matched_shop = XhsDiscoveryMatchedShop(
                    shop_id=str(shop.get("shop_id")),
                    shop_name=discovered_name or profile_name,
                    name_matches_profile_map=name_matches,
                )
            except WorkerError as exc:
                status = "shop_unmatched"
                errors.append(exc.error_message)

        context = XhsAccountBindingContext(
            job_type=normalized,
            job_id=job_id,
            account_id=account_id,
            status=status,
            profile_map={
                "exists": self.profile_map_path.exists(),
                "valid": profile_error is None,
                "account_found": account_found,
                "profile_map_path": str(self.profile_map_path),
            },
            mapped_profile=mapped_profile,
            discovery={
                "evidence_exists": discovery_exists,
                "shop_found": shop_found,
                "shop_count": len((discovery or {}).get("shops") or []),
                "discovery_evidence_path": str(self.discovery_evidence_path),
            },
            matched_shop=matched_shop,
            warnings=warnings,
            errors=errors,
            safe_mode=True,
            real_actions={
                "opened_shop": False,
                "closed_shop": False,
                "opened_xhs": False,
                "called_yingdao_openapi": False,
                "real_search_executed": False,
                "real_publish_executed": False,
            },
        )
        return self._model_to_dict(context)

    def attach_binding_to_actual_form_fill_input(
        self,
        actual_form_fill_input_path: str,
        binding_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Attach account_binding into actual_form_fill_input.json."""
        path = Path(actual_form_fill_input_path)
        payload = self._read_json(path, XHS_ACCOUNT_BINDING_ERROR)
        profile = binding_context.get("mapped_profile") or {}
        payload["account_binding"] = {
            "account_id": binding_context.get("account_id"),
            "shop_id": profile.get("shop_id"),
            "shop_name": profile.get("shop_name"),
            "provider_type": profile.get("provider_type"),
            "binding_status": binding_context.get("status"),
            "account_binding_context_path": self.get_binding_paths(binding_context["job_type"], binding_context["job_id"])["context_path"],
            "opened_shop": False,
            "opened_xhs": False,
        }
        self._write_json(path, payload)
        return payload

    def write_account_binding_package(
        self,
        job_type: str,
        job_id: str,
        input_json: dict[str, Any],
        context_json: dict[str, Any],
    ) -> dict[str, str]:
        """Write account binding input and context files."""
        paths = self.get_binding_paths(job_type, job_id)
        return {
            "account_binding_input_path": self._write_json(Path(paths["input_path"]), input_json),
            "account_binding_context_path": self._write_json(Path(paths["context_path"]), context_json),
        }

    def read_account_binding_confirmation(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read account_binding_confirmation.json."""
        path = Path(self.get_binding_paths(job_type, job_id)["confirmation_path"])
        if not path.exists():
            raise WorkerError(
                XHS_ACCOUNT_BINDING_CONFIRMATION_NOT_FOUND,
                f"account binding confirmation not found: {path}",
            )
        return self._read_json(path, XHS_ACCOUNT_BINDING_CONFIRMATION_INVALID)

    def validate_account_binding_confirmation(
        self,
        confirmation: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate confirmation against context and safety flags."""
        if not isinstance(confirmation, dict):
            raise WorkerError(XHS_ACCOUNT_BINDING_CONFIRMATION_INVALID, "confirmation must be a JSON object")
        runtime = confirmation.get("runtime") or {}
        for flag in (
            "opened_shop",
            "closed_shop",
            "opened_xhs",
            "opened_external_url",
            "called_yingdao_openapi",
            "called_kuaijingvs_open_shop",
        ):
            if runtime.get(flag) is True:
                raise WorkerError(XHS_ACCOUNT_BINDING_FORBIDDEN_ACTION, f"account binding confirmation has forbidden flag {flag}=true")
        if runtime.get("real_search_executed") is True or runtime.get("real_publish_executed") is True:
            raise WorkerError(XHS_ACCOUNT_BINDING_REAL_ACTION_FORBIDDEN, "account binding confirmation reports real search or publish")
        if confirmation.get("account_id") != context.get("account_id"):
            raise WorkerError(XHS_ACCOUNT_BINDING_CONFIRMATION_INVALID, "confirmation account_id does not match context")
        confirmed = confirmation.get("confirmed_profile") or {}
        profile = context.get("mapped_profile") or {}
        if profile and confirmed.get("shop_id") != profile.get("shop_id"):
            raise WorkerError(XHS_ACCOUNT_BINDING_SHOP_UNMATCHED, "confirmation shop_id does not match context")
        return confirmation

    def verify_account_binding(self, job_type: str, job_id: str) -> XhsAccountBindingVerifyResult:
        """Verify account binding confirmation."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_binding_paths(normalized, job_id)
        context = self._read_json(Path(paths["context_path"]), XHS_ACCOUNT_BINDING_ERROR)
        summary = XhsAccountBindingSummary(
            binding_status=context.get("status"),
            account_id=context.get("account_id"),
            shop_id=(context.get("mapped_profile") or {}).get("shop_id"),
            warnings=context.get("warnings") or [],
            errors=context.get("errors") or [],
        )
        confirmation = None
        status = "verified"
        message = "XHS account binding confirmation verified"
        error_code = None
        error_message = None
        try:
            confirmation = self.read_account_binding_confirmation(normalized, job_id)
            summary.confirmation_exists = True
            self.validate_account_binding_confirmation(confirmation, context)
            summary.confirmation_valid = True
            runtime = confirmation.get("runtime") or {}
            summary.opened_shop = bool(runtime.get("opened_shop", False))
            summary.closed_shop = bool(runtime.get("closed_shop", False))
            summary.opened_xhs = bool(runtime.get("opened_xhs", False))
            summary.opened_external_url = bool(runtime.get("opened_external_url", False))
            summary.called_yingdao_openapi = bool(runtime.get("called_yingdao_openapi", False))
            summary.called_kuaijingvs_open_shop = bool(runtime.get("called_kuaijingvs_open_shop", False))
            summary.real_action_executed = bool(runtime.get("real_search_executed") or runtime.get("real_publish_executed"))
        except WorkerError as exc:
            if exc.error_code == XHS_ACCOUNT_BINDING_CONFIRMATION_NOT_FOUND:
                status = "waiting_account_binding_confirmation"
                message = "Waiting for account_binding_confirmation.json"
            else:
                status = "failed"
                message = "account binding confirmation invalid"
            error_code = exc.error_code
            error_message = exc.error_message
        result = XhsAccountBindingVerifyResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            account_binding_dir=paths["binding_dir"],
            confirmation_path=paths["confirmation_path"],
            account_binding_summary_path=paths["summary_path"],
            summary=summary,
            confirmation=confirmation,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        self.write_account_binding_summary(self._model_to_dict(result))
        return result

    def write_mock_confirmation(self, job_type: str, job_id: str, status: str = "success") -> dict[str, str]:
        """Write local account binding confirmation."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_binding_paths(normalized, job_id)
        context = self._read_json(Path(paths["context_path"]), XHS_ACCOUNT_BINDING_ERROR)
        profile = context.get("mapped_profile") or {
            "account_id": context.get("account_id"),
            "shop_id": None,
            "shop_name": None,
            "provider_type": "kuaijingvs_yingdao_rpa",
        }
        confirmation = self._model_to_dict(
            XhsAccountBindingConfirmation(
                job_type=normalized,
                job_id=job_id,
                account_id=str(context.get("account_id")),
                status=status,
                confirmed_at=self._utc_now(),
                confirmed_profile=XhsMappedProfile(**profile),
                runtime=XhsAccountBindingConfirmationRuntime(),
                notes="Confirmed account binding against local profile map and readonly discovery evidence only.",
            )
        )
        return {"confirmation_path": self._write_json(Path(paths["confirmation_path"]), confirmation)}

    def write_account_binding_summary(self, summary: dict[str, Any]) -> str:
        """Write account binding summary."""
        paths = self.get_binding_paths(str(summary["job_type"]), str(summary["job_id"]))
        return self._write_json(Path(paths["summary_path"]), summary)

    def load_hardened_discovery(self, hardened_path: str | Path) -> dict[str, Any]:
        """Load local hardened KuaJingVS discovery evidence."""
        path = self._resolve_worker_path(hardened_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_MISSING, f"hardened discovery not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_UNSAFE, f"hardened discovery JSON invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_UNSAFE, "hardened discovery must be a JSON object")
        return payload

    def validate_strict_rules(
        self,
        profile_map: dict[str, Any],
        hardened_discovery: dict[str, Any],
        account_id: str,
        rules: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate strict account binding rules."""
        checks = {
            "profile_map_exists": True,
            "profile_map_valid": True,
            "account_found": False,
            "hardened_discovery_exists": True,
            "hardened_discovery_safe": False,
            "shop_id_matched": False,
            "shop_name_matched": False,
            "provider_type_allowed": False,
            "sensitive_field_absent": False,
        }
        warnings: list[str] = []
        errors: list[str] = []
        profile = profile_map.get(account_id)
        if not isinstance(profile, dict):
            return self._strict_validation_result(
                "account_not_found",
                XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND,
                f"account_id not found in profile map: {account_id}",
                checks,
                warnings,
                errors,
            )
        checks["account_found"] = True
        provider_type = str(profile.get("provider_type") or "")
        if provider_type not in ALLOWED_PROFILE_PROVIDER_TYPES:
            return self._strict_validation_result(
                "provider_type_invalid",
                XHS_ACCOUNT_BINDING_STRICT_PROVIDER_TYPE_INVALID,
                f"provider_type invalid for strict binding: {provider_type}",
                {**checks, "provider_type_allowed": False},
                warnings,
                errors,
                profile=profile,
            )
        checks["provider_type_allowed"] = True
        hardened_safe = (
            hardened_discovery.get("status") == "success"
            and bool((hardened_discovery.get("sanitization") or {}).get("sensitive_value_scan_passed", False))
            and not any((hardened_discovery.get("forbidden") or {}).values())
            and not (hardened_discovery.get("errors") or [])
        )
        checks["hardened_discovery_safe"] = hardened_safe
        checks["sensitive_field_absent"] = hardened_safe
        if not hardened_safe:
            return self._strict_validation_result(
                "hardened_discovery_unsafe",
                XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_UNSAFE,
                "hardened discovery is unsafe or failed validation",
                checks,
                warnings,
                errors,
                profile=profile,
            )
        shop_id = str(profile.get("shop_id") or "")
        matched_shop = None
        for shop in hardened_discovery.get("shops") or []:
            if str(shop.get("shop_id")) == shop_id:
                matched_shop = shop
                break
        if matched_shop is None:
            return self._strict_validation_result(
                "shop_unmatched",
                XHS_ACCOUNT_BINDING_STRICT_SHOP_UNMATCHED,
                f"shop_id not matched in hardened discovery: {shop_id}",
                checks,
                warnings,
                errors,
                profile=profile,
            )
        checks["shop_id_matched"] = True
        profile_name = str(profile.get("shop_name") or "")
        shop_name = str(matched_shop.get("shop_name") or "")
        checks["shop_name_matched"] = bool(profile_name and shop_name and profile_name == shop_name)
        if not checks["shop_name_matched"]:
            message = "shop_name mismatch between profile map and hardened discovery"
            if rules.get("fail_on_name_mismatch", True) or rules.get("require_shop_name_match", True):
                return self._strict_validation_result(
                    "shop_name_mismatch",
                    XHS_ACCOUNT_BINDING_STRICT_SHOP_NAME_MISMATCH,
                    message,
                    checks,
                    warnings,
                    errors,
                    profile=profile,
                    matched_shop=matched_shop,
                )
            warnings.append(message)
        return self._strict_validation_result(
            "strict_matched",
            None,
            None,
            checks,
            warnings,
            errors,
            profile=profile,
            matched_shop=matched_shop,
        )

    def write_strict_binding_input(self, job_type: str, job_id: str, input_json: dict[str, Any]) -> str:
        """Write strict binding input JSON."""
        return self._write_json(Path(self.get_strict_binding_paths(job_type, job_id)["input_path"]), input_json)

    def write_strict_binding_result(self, job_type: str, job_id: str, result_json: dict[str, Any]) -> str:
        """Write strict binding result JSON."""
        return self._write_json(Path(self.get_strict_binding_paths(job_type, job_id)["result_path"]), result_json)

    def write_strict_binding_summary(self, summary: dict[str, Any]) -> str:
        """Write strict binding summary JSON."""
        return self._write_json(Path(self.get_strict_binding_paths(summary["job_type"], summary["job_id"])["summary_path"]), summary)

    def get_binding_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return account binding file paths."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        binding_dir = self.queue_root / "account_binding" / category / job_id
        return {
            "binding_dir": str(binding_dir),
            "input_path": str(binding_dir / "account_binding_input.json"),
            "context_path": str(binding_dir / "account_binding_context.json"),
            "confirmation_path": str(binding_dir / "account_binding_confirmation.json"),
            "summary_path": str(binding_dir / "account_binding_summary.json"),
        }

    def get_strict_binding_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return strict account binding file paths."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        strict_dir = self.queue_root / "account_binding" / "strict" / category / job_id
        return {
            "strict_binding_dir": str(strict_dir),
            "input_path": str(strict_dir / "strict_binding_input.json"),
            "result_path": str(strict_dir / "strict_binding_result.json"),
            "summary_path": str(strict_dir / "strict_binding_summary.json"),
        }

    def _prepare_binding(
        self,
        job_type: str,
        job_id: str,
        account_id: str,
        actual_form_fill_input_path: str,
    ) -> XhsAccountBindingPrepareResult:
        normalized = self._normalize_job_type(job_type)
        paths = self.get_binding_paths(normalized, job_id)
        input_json = self._model_to_dict(
            XhsAccountBindingInput(
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                created_at=self._utc_now(),
                profile_map_path=str(self.profile_map_path),
                kuaijingvs_discovery_evidence_path=str(self.discovery_evidence_path),
                actual_form_fill_input_path=actual_form_fill_input_path,
                forbidden={
                    "open_shop": True,
                    "close_shop": True,
                    "open_xhs": True,
                    "open_external_url": True,
                    "real_search": True,
                    "real_publish": True,
                    "yingdao_openapi": True,
                },
            )
        )
        profile = None
        discovery = None
        profile_error = None
        discovery_error = None
        try:
            profile_map = self.load_profile_map(self.profile_map_path)
            profile = self.resolve_account_profile(account_id, profile_map)
        except WorkerError as exc:
            profile_error = exc
            if exc.error_code == XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND:
                profile = None
        try:
            discovery = self.load_kuaijingvs_discovery_evidence(self.discovery_evidence_path)
        except WorkerError as exc:
            discovery_error = exc
        context = self.build_account_binding_context(
            normalized,
            job_id,
            account_id,
            profile,
            discovery,
            profile_error=profile_error,
            discovery_error=discovery_error,
        )
        self.write_account_binding_package(normalized, job_id, input_json, context)
        self.attach_binding_to_actual_form_fill_input(actual_form_fill_input_path, context)
        binding_status = context["status"]
        severe = {
            "profile_map_missing": XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING,
            "profile_map_invalid": XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID,
            "account_not_found": XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND,
            "shop_unmatched": XHS_ACCOUNT_BINDING_SHOP_UNMATCHED,
        }
        error_code = severe.get(binding_status)
        error_message = "; ".join(context.get("errors") or []) or None
        status = "failed" if error_code else "waiting_account_binding_confirmation"
        return XhsAccountBindingPrepareResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            binding_status=binding_status,
            account_binding_dir=paths["binding_dir"],
            account_binding_input_path=paths["input_path"],
            account_binding_context_path=paths["context_path"],
            actual_form_fill_input_path=actual_form_fill_input_path,
            confirmation_path=paths["confirmation_path"],
            message="XHS account binding context prepared without opening shop or XHS",
            error_code=error_code,
            error_message=error_message,
        )

    def _prepare_strict_binding(self, job_type: str, job_id: str, account_id: str) -> XhsAccountBindingStrictResult:
        normalized = self._normalize_job_type(job_type)
        paths = self.get_strict_binding_paths(normalized, job_id)
        rules = XhsAccountBindingStrictRules(
            require_hardened_discovery=self._truthy(os.getenv("XHS_ACCOUNT_BINDING_REQUIRE_HARDENED_DISCOVERY", "true")),
            require_shop_name_match=self._truthy(os.getenv("XHS_ACCOUNT_BINDING_FAIL_ON_SHOP_NAME_MISMATCH", "true")),
            fail_on_name_mismatch=self._truthy(os.getenv("XHS_ACCOUNT_BINDING_FAIL_ON_SHOP_NAME_MISMATCH", "true")),
        )
        normal_context_path = self.get_binding_paths(normalized, job_id)["context_path"]
        input_json = self._model_to_dict(
            XhsAccountBindingStrictInput(
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                created_at=self._utc_now(),
                profile_map_path=str(self.profile_map_path),
                hardened_discovery_path=str(self.hardened_discovery_path),
                account_binding_context_path=normal_context_path,
                strict_rules=rules,
                forbidden={
                    "open_shop": True,
                    "close_shop": True,
                    "open_xhs": True,
                    "real_search": True,
                    "real_publish": True,
                    "yingdao_openapi": True,
                },
            )
        )
        self.write_strict_binding_input(normalized, job_id, input_json)
        checks = {
            "profile_map_exists": self.profile_map_path.exists(),
            "profile_map_valid": False,
            "account_found": False,
            "hardened_discovery_exists": self.hardened_discovery_path.exists(),
            "hardened_discovery_safe": False,
            "shop_id_matched": False,
            "shop_name_matched": False,
            "provider_type_allowed": False,
            "sensitive_field_absent": False,
        }
        try:
            profile_map = self._load_profile_map_for_strict()
            checks["profile_map_valid"] = True
            hardened = self.load_hardened_discovery(self.hardened_discovery_path)
            validation = self.validate_strict_rules(profile_map, hardened, account_id, self._model_to_dict(rules))
        except WorkerError as exc:
            binding_status = self._strict_status_for_error(exc.error_code)
            validation = {
                "binding_status": binding_status,
                "status": "failed",
                "error_code": exc.error_code,
                "error_message": exc.error_message,
                "checks": checks,
                "matched_profile": None,
                "matched_shop": None,
                "warnings": [],
                "errors": [exc.error_message],
            }
        result = self._model_to_dict(
            XhsAccountBindingStrictResult(
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                status=validation["status"],
                binding_status=validation["binding_status"],
                checked_at=self._utc_now(),
                checks=validation["checks"],
                matched_profile=XhsMappedProfile(account_id=account_id, **validation["matched_profile"])
                if validation.get("matched_profile")
                else None,
                matched_shop=validation.get("matched_shop"),
                warnings=validation.get("warnings") or [],
                errors=validation.get("errors") or [],
                real_actions={
                    "opened_shop": False,
                    "closed_shop": False,
                    "opened_xhs": False,
                    "called_yingdao_openapi": False,
                    "real_search_executed": False,
                    "real_publish_executed": False,
                },
                strict_binding_dir=paths["strict_binding_dir"],
                strict_binding_input_path=paths["input_path"],
                strict_binding_result_path=paths["result_path"],
                strict_binding_summary_path=paths["summary_path"],
                error_code=validation.get("error_code"),
                error_message=validation.get("error_message"),
            )
        )
        self.write_strict_binding_result(normalized, job_id, result)
        summary = self._model_to_dict(
            XhsAccountBindingStrictSummary(
                status=result["status"],
                binding_status=result["binding_status"],
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                strict_binding_result_path=paths["result_path"],
                profile_map_exists=result["checks"].get("profile_map_exists", False),
                hardened_discovery_exists=result["checks"].get("hardened_discovery_exists", False),
                shop_id_matched=result["checks"].get("shop_id_matched", False),
                shop_name_matched=result["checks"].get("shop_name_matched", False),
                provider_type_allowed=result["checks"].get("provider_type_allowed", False),
                error_code=result.get("error_code"),
                error_message=result.get("error_message"),
            )
        )
        self.write_strict_binding_summary(summary)
        return XhsAccountBindingStrictResult(**result)

    def _strict_validation_result(
        self,
        binding_status: str,
        error_code: str | None,
        error_message: str | None,
        checks: dict[str, bool],
        warnings: list[str],
        errors: list[str],
        profile: dict[str, Any] | None = None,
        matched_shop: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if error_message:
            errors = [*errors, error_message]
        return {
            "binding_status": binding_status,
            "status": "success" if error_code is None else "failed",
            "error_code": error_code,
            "error_message": error_message,
            "checks": checks,
            "matched_profile": profile,
            "matched_shop": matched_shop,
            "warnings": warnings,
            "errors": errors,
        }

    def _load_profile_map_for_strict(self) -> dict[str, Any]:
        path = self.profile_map_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING, f"profile map not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID, f"profile map JSON invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID, "profile map must be a JSON object")
        for account_id, profile in payload.items():
            if not isinstance(profile, dict):
                raise WorkerError(XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID, f"profile map entry must be object: {account_id}")
            missing = [field for field in ("shop_id", "shop_name", "provider_type") if not profile.get(field)]
            if missing:
                raise WorkerError(
                    XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID,
                    f"profile map entry {account_id} missing fields: {', '.join(missing)}",
                )
        return payload

    def _strict_status_for_error(self, error_code: str) -> str:
        return {
            XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING: "profile_map_missing",
            XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID: "profile_map_invalid",
            XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND: "account_not_found",
            XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_MISSING: "hardened_discovery_missing",
            XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_UNSAFE: "hardened_discovery_unsafe",
            XHS_ACCOUNT_BINDING_STRICT_SHOP_UNMATCHED: "shop_unmatched",
            XHS_ACCOUNT_BINDING_STRICT_SHOP_NAME_MISMATCH: "shop_name_mismatch",
            XHS_ACCOUNT_BINDING_STRICT_PROVIDER_TYPE_INVALID: "provider_type_invalid",
        }.get(error_code, "failed")

    def _read_json(self, path: Path, error_code: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(error_code, f"JSON file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(error_code, f"JSON file invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(error_code, f"JSON file must contain an object: {path}")
        return payload

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(XHS_ACCOUNT_BINDING_ERROR, f"failed to write account binding JSON: {path}: {exc}") from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_ACCOUNT_BINDING_ERROR, f"unsupported account binding job_type: {job_type}")

    def _resolve_worker_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _truthy(self, value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
