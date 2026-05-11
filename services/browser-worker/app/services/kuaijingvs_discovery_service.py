import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.integrations.kuaijingvs_adapter import KuaJingVSAdapter
from app.schemas.xhs_kuaijingvs import KuaJingVSDiscoveryResult
from app.services.external_readiness_service import ALLOWED_PROFILE_PROVIDER_TYPES
from app.utils.errors import (
    XHS_EXTERNAL_PROFILE_MAP_INVALID,
    XHS_KJVS_PROFILE_MAP_UNMATCHED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class KuaJingVSDiscoveryService:
    """KuaJingVS live-readonly discovery and profile-map matching."""

    def __init__(
        self,
        adapter: KuaJingVSAdapter | None = None,
        profile_map_path: str | Path | None = None,
        evidence_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create a discovery service."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.adapter = adapter or KuaJingVSAdapter()
        self.profile_map_path = profile_map_path or os.getenv("KJVS_PROFILE_MAP_PATH", ".config/kuaijingvs_profiles.json")
        self.evidence_root = self._resolve_worker_path(evidence_root or os.getenv("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence"))

    def discover(self) -> KuaJingVSDiscoveryResult:
        """Run live-readonly KuaJingVS discovery and save local evidence."""
        shops = self.adapter.list_shops_readonly()
        profile_map_path = self._resolve_worker_path(self.profile_map_path)
        profile_map_exists = profile_map_path.exists()
        profile_map = {}
        if profile_map_exists:
            try:
                profile_map = self.load_profile_map(profile_map_path)
                validation = self.validate_profile_map(profile_map)
            except WorkerError as exc:
                validation = {
                    "valid": False,
                    "error_code": exc.error_code,
                    "error_message": exc.error_message,
                }
        else:
            validation = {
                "valid": False,
                "error_code": XHS_EXTERNAL_PROFILE_MAP_INVALID,
                "error_message": f"profile map not found: {profile_map_path}",
            }
        match = self.match_profile_map_to_shops(profile_map if validation["valid"] else {}, shops)
        status = "success"
        error_code = None
        error_message = None
        if not validation["valid"]:
            status = "failed"
            error_code = validation.get("error_code")
            error_message = validation.get("error_message")
        result = {
            "status": status,
            "mode": "live_readonly",
            "safe_mode": True,
            "api_base_url_configured": bool(self.adapter.api_base_url),
            "live_readonly_enabled": self.adapter.is_live_readonly_enabled(),
            "shop_count": len(shops),
            "shops": shops,
            "profile_map_path": str(profile_map_path),
            "profile_map_exists": profile_map_exists,
            "profile_map_valid": bool(validation["valid"]),
            "matched_accounts": match["matched_accounts"],
            "unmatched_accounts": match["unmatched_accounts"],
            "unmapped_shops": match["unmapped_shops"],
            "matched_account_count": len(match["matched_accounts"]),
            "unmatched_account_count": len(match["unmatched_accounts"]),
            "error_code": error_code,
            "error_message": error_message,
        }
        result["evidence_json_path"] = self.save_discovery_evidence(result)
        return KuaJingVSDiscoveryResult(**result)

    def load_profile_map(self, path: str | Path) -> dict:
        """Load profile map JSON."""
        profile_path = Path(path)
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkerError(
                error_code=XHS_EXTERNAL_PROFILE_MAP_INVALID,
                error_message=f"profile map JSON invalid: {profile_path}: {exc}",
                retryable=False,
            ) from exc
        except OSError as exc:
            raise WorkerError(
                error_code=XHS_EXTERNAL_PROFILE_MAP_INVALID,
                error_message=f"profile map cannot be read: {profile_path}: {exc}",
                retryable=False,
            ) from exc
        if not isinstance(payload, dict):
            raise WorkerError(
                error_code=XHS_EXTERNAL_PROFILE_MAP_INVALID,
                error_message="profile map must be a JSON object",
                retryable=False,
            )
        return payload

    def validate_profile_map(self, profile_map: dict) -> dict:
        """Validate profile map structure."""
        if not isinstance(profile_map, dict):
            return self._invalid("profile map must be a JSON object")
        for account_id, profile in profile_map.items():
            if not isinstance(profile, dict):
                return self._invalid(f"profile map entry must be an object: {account_id}")
            missing = [field for field in ("shop_id", "shop_name", "provider_type") if not profile.get(field)]
            if missing:
                return self._invalid(f"profile map entry {account_id} missing fields: {', '.join(missing)}")
            provider_type = str(profile.get("provider_type"))
            if provider_type not in ALLOWED_PROFILE_PROVIDER_TYPES:
                return self._invalid(f"profile map entry {account_id} has unsupported provider_type: {provider_type}")
        return {"valid": True, "error_code": None, "error_message": None}

    def match_profile_map_to_shops(self, profile_map: dict, shops: list[dict]) -> dict:
        """Match account profile map entries to discovered shops."""
        shops_by_id = {str(shop.get("shop_id")): shop for shop in shops if shop.get("shop_id") is not None}
        mapped_shop_ids = set()
        matched_accounts = []
        unmatched_accounts = []
        for account_id, profile in profile_map.items():
            shop_id = str(profile.get("shop_id"))
            expected_name = str(profile.get("shop_name"))
            shop = shops_by_id.get(shop_id)
            if shop is None:
                unmatched_accounts.append(
                    {
                        "account_id": account_id,
                        "shop_id": shop_id,
                        "shop_name": expected_name,
                        "matched": False,
                        "warning": "shop_id not found in KuaJingVS discovery",
                    }
                )
                continue
            mapped_shop_ids.add(shop_id)
            discovered_name = shop.get("shop_name")
            warning = None
            if discovered_name and expected_name and str(discovered_name) != expected_name:
                warning = "shop_name differs from discovery"
            matched_accounts.append(
                {
                    "account_id": account_id,
                    "shop_id": shop_id,
                    "shop_name": str(discovered_name or expected_name),
                    "matched": True,
                    "warning": warning,
                }
            )
        unmapped_shops = [shop for shop in shops if str(shop.get("shop_id")) not in mapped_shop_ids]
        return {
            "matched_accounts": matched_accounts,
            "unmatched_accounts": unmatched_accounts,
            "unmapped_shops": unmapped_shops,
            "error_code": XHS_KJVS_PROFILE_MAP_UNMATCHED if unmatched_accounts else None,
        }

    def save_discovery_evidence(self, result: dict, output_dir: str | Path | None = None) -> str:
        """Write discovery evidence JSON locally."""
        target_dir = self._resolve_worker_path(output_dir) if output_dir else self.evidence_root / "kuaijingvs_discovery"
        target_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = target_dir / "discovery.json"
        payload = {
            **result,
            "saved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        evidence_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(evidence_path)

    def _invalid(self, message: str) -> dict:
        """Return an invalid profile map result."""
        return {
            "valid": False,
            "error_code": XHS_EXTERNAL_PROFILE_MAP_INVALID,
            "error_message": message,
        }

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _model_to_dict(self, value: Any) -> dict:
        """Convert Pydantic models to dictionaries across versions."""
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)
