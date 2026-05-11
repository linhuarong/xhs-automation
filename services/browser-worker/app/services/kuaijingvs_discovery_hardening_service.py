import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    KuaJingVSDiscoveryHardenResult,
    KuaJingVSHardenedDiscoveryEvidence,
    KuaJingVSHardenedDiscoverySummary,
    KuaJingVSHardenedShop,
    KuaJingVSSanitizationResult,
)
from app.utils.errors import (
    XHS_KJVS_DISCOVERY_HARDENED_INVALID,
    XHS_KJVS_DISCOVERY_HASH_FAILED,
    XHS_KJVS_DISCOVERY_SENSITIVE_FIELD_DETECTED,
    XHS_KJVS_DISCOVERY_SENSITIVE_VALUE_DETECTED,
    XHS_KJVS_DISCOVERY_SOURCE_NOT_FOUND,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]

SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "set-cookie",
    "secret",
    "password",
    "passwd",
    "authorization",
    "auth",
    "api_key",
    "app_secret",
    "session",
    "credential",
    "private_key",
}
SENSITIVE_VALUE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"Bearer\s+",
        r"Cookie:",
        r"sessionid=",
        r"access_token=",
        r"refresh_token=",
        r"password=",
        r"secret=",
        r"Authorization",
    )
]


class KuaJingVSDiscoveryHardeningService:
    """Harden local KuaJingVS readonly discovery evidence without live calls."""

    def __init__(
        self,
        source_path: str | Path | None = None,
        hardened_path: str | Path | None = None,
        summary_path: str | Path | None = None,
        audit_path: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.source_path = self._resolve_worker_path(
            source_path or os.getenv("KJVS_DISCOVERY_SOURCE_PATH", ".local_evidence/kuaijingvs_discovery/discovery.json")
        )
        self.hardened_path = self._resolve_worker_path(
            hardened_path
            or os.getenv("KJVS_DISCOVERY_HARDENED_PATH", ".local_evidence/kuaijingvs_discovery/hardened_discovery.json")
        )
        self.summary_path = self._resolve_worker_path(
            summary_path
            or os.getenv(
                "KJVS_DISCOVERY_HARDENED_SUMMARY_PATH",
                ".local_evidence/kuaijingvs_discovery/hardened_discovery_summary.json",
            )
        )
        self.audit_path = self._resolve_worker_path(audit_path or ".local_evidence/kuaijingvs_discovery/hardened_discovery_audit.json")
        self.fail_on_sensitive_value = self._truthy(os.getenv("KJVS_DISCOVERY_FAIL_ON_SENSITIVE_VALUE", "true"))

    def harden_discovery_evidence(self, source_path: str | Path | None = None) -> KuaJingVSDiscoveryHardenResult:
        """Read local discovery evidence and write hardened evidence plus summary."""
        actual_source = self._resolve_worker_path(source_path) if source_path else self.source_path
        try:
            source = self.load_source_evidence(actual_source)
            hardened = self.sanitize_discovery(source, actual_source)
            validation = self.validate_hardened_evidence(hardened)
            hardened["status"] = "success" if validation["valid"] else "failed"
            hardened["errors"].extend(validation["errors"])
            hardened["evidence_hash"] = self.compute_evidence_hash(hardened)
            hardened_path = self.write_hardened_evidence(hardened)
            summary = self._build_summary(hardened, actual_source, hardened_path)
            summary_path = self.write_hardened_summary(summary)
            self._write_json(self.audit_path, {"generated_at": self._utc_now(), "summary": summary})
            return KuaJingVSDiscoveryHardenResult(
                status=hardened["status"],
                hardened_evidence_path=hardened_path,
                summary_path=summary_path,
                audit_path=str(self.audit_path),
                shop_count=hardened["shop_count"],
                sensitive_value_scan_passed=hardened["sanitization"]["sensitive_value_scan_passed"],
                evidence_hash=hardened.get("evidence_hash"),
                summary=summary,
                error_code=None if hardened["status"] == "success" else XHS_KJVS_DISCOVERY_HARDENED_INVALID,
                error_message=None if hardened["status"] == "success" else "; ".join(hardened["errors"]),
            )
        except WorkerError as exc:
            summary = {
                "schema_version": "1.0",
                "summary_type": "kuaijingvs_readonly_discovery_hardened_summary",
                "status": "failed",
                "generated_at": self._utc_now(),
                "source_evidence_path": str(actual_source),
                "hardened_evidence_path": str(self.hardened_path),
                "shop_count": 0,
                "safe_shop_count": 0,
                "warning_count": 0,
                "error_count": 1,
                "sensitive_key_removed_count": 0,
                "sensitive_value_scan_passed": exc.error_code != XHS_KJVS_DISCOVERY_SENSITIVE_VALUE_DETECTED,
                "evidence_hash": None,
                "ready_for_strict_account_binding": False,
                "error_code": exc.error_code,
                "error_message": exc.error_message,
            }
            summary_path = self.write_hardened_summary(summary)
            return KuaJingVSDiscoveryHardenResult(
                status="failed",
                hardened_evidence_path=None,
                summary_path=summary_path,
                shop_count=0,
                sensitive_value_scan_passed=summary["sensitive_value_scan_passed"],
                evidence_hash=None,
                summary=summary,
                error_code=exc.error_code,
                error_message=exc.error_message,
            )

    def load_source_evidence(self, source_path: str | Path) -> dict[str, Any]:
        """Load local source discovery evidence."""
        path = self._resolve_worker_path(source_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(XHS_KJVS_DISCOVERY_SOURCE_NOT_FOUND, f"source discovery evidence not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(XHS_KJVS_DISCOVERY_HARDENED_INVALID, f"source discovery evidence JSON invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(XHS_KJVS_DISCOVERY_HARDENED_INVALID, "source discovery evidence must be a JSON object")
        return payload

    def sanitize_discovery(self, source: dict[str, Any], source_path: str | Path | None = None) -> dict[str, Any]:
        """Normalize safe fields and reject sensitive values."""
        sensitive_values = self.scan_sensitive_values(source)
        if sensitive_values["detected"] and self.fail_on_sensitive_value:
            raise WorkerError(
                XHS_KJVS_DISCOVERY_SENSITIVE_VALUE_DETECTED,
                f"sensitive value pattern detected: {', '.join(sensitive_values['patterns'])}",
            )
        removed_keys: set[str] = set()
        self.remove_sensitive_fields(source, removed_keys)
        shops = [self.normalize_shop(shop) for shop in self._extract_shops(source)]
        warnings: list[str] = []
        errors: list[str] = []
        for shop in shops:
            if not shop["shop_id"] or not shop["shop_name"]:
                shop["safe"] = False
                shop["warnings"].append("shop_id or shop_name missing")
                errors.append("shop_id or shop_name missing in discovery shop")
        forbidden = {
            "contains_token": False,
            "contains_cookie": False,
            "contains_secret": False,
            "contains_password": False,
            "contains_auth_header": False,
            "opened_shop": False,
            "opened_xhs": False,
            "called_yingdao_openapi": False,
        }
        return self._model_to_dict(
            KuaJingVSHardenedDiscoveryEvidence(
                status="failed" if errors or sensitive_values["detected"] else "success",
                source_evidence_path=str(source_path or self.source_path),
                generated_at=self._utc_now(),
                sanitization=KuaJingVSSanitizationResult(
                    sensitive_keys_removed=sorted(removed_keys),
                    sensitive_value_scan_passed=not sensitive_values["detected"],
                ),
                shop_count=len(shops),
                shops=[KuaJingVSHardenedShop(**shop) for shop in shops],
                evidence_hash=None,
                warnings=warnings,
                errors=errors,
                forbidden=forbidden,
            )
        )

    def normalize_shop(self, raw_shop: dict[str, Any]) -> dict[str, Any]:
        """Normalize one raw shop into safe fields only."""
        if not isinstance(raw_shop, dict):
            raw_shop = {}
        shop_id = raw_shop.get("shop_id") or raw_shop.get("shopId") or raw_shop.get("id") or raw_shop.get("shopID")
        shop_name = raw_shop.get("shop_name") or raw_shop.get("shopName") or raw_shop.get("name") or raw_shop.get("title")
        provider_type = raw_shop.get("provider_type") or raw_shop.get("providerType") or "kuaijingvs_yingdao_rpa"
        return {
            "shop_id": str(shop_id or ""),
            "shop_name": str(shop_name or ""),
            "normalized_shop_name": str(shop_name or "").strip(),
            "provider_type": str(provider_type or "kuaijingvs_yingdao_rpa"),
            "raw_keys": self.extract_raw_keys(raw_shop),
            "safe": True,
            "warnings": [],
        }

    def extract_raw_keys(self, raw_shop: dict[str, Any]) -> list[str]:
        """Return non-sensitive source keys without raw values."""
        return sorted(str(key) for key in raw_shop.keys() if not self._is_sensitive_key(str(key)))

    def remove_sensitive_fields(self, value: Any, removed_keys: set[str] | None = None) -> Any:
        """Return a copy with sensitive dict keys removed."""
        removed = removed_keys if removed_keys is not None else set()
        if isinstance(value, dict):
            clean = {}
            for key, nested in value.items():
                key_text = str(key)
                if self._is_sensitive_key(key_text):
                    removed.add(key_text)
                    continue
                clean[key] = self.remove_sensitive_fields(nested, removed)
            return clean
        if isinstance(value, list):
            return [self.remove_sensitive_fields(item, removed) for item in value]
        return value

    def scan_sensitive_values(self, value: Any) -> dict[str, Any]:
        """Scan values for common secret-bearing patterns."""
        found: set[str] = set()

        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for nested in item.values():
                    walk(nested)
            elif isinstance(item, list):
                for nested in item:
                    walk(nested)
            elif isinstance(item, str):
                for pattern in SENSITIVE_VALUE_PATTERNS:
                    if pattern.search(item):
                        found.add(pattern.pattern)

        walk(value)
        return {"detected": bool(found), "patterns": sorted(found)}

    def compute_evidence_hash(self, hardened: dict[str, Any]) -> str:
        """Compute stable SHA-256 hash for hardened evidence."""
        try:
            payload = dict(hardened)
            payload["evidence_hash"] = None
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        except Exception as exc:
            raise WorkerError(XHS_KJVS_DISCOVERY_HASH_FAILED, f"failed to hash hardened evidence: {exc}") from exc

    def write_hardened_evidence(self, hardened: dict[str, Any]) -> str:
        """Write hardened discovery JSON."""
        return self._write_json(self.hardened_path, hardened)

    def write_hardened_summary(self, summary: dict[str, Any]) -> str:
        """Write hardened discovery summary JSON."""
        return self._write_json(self.summary_path, summary)

    def validate_hardened_evidence(self, hardened: dict[str, Any]) -> dict[str, Any]:
        """Validate hardened evidence does not contain forbidden fields or values."""
        forbidden_keys = sorted(self._find_sensitive_keys(hardened))
        value_scan_target = json.loads(json.dumps(hardened, ensure_ascii=False))
        if isinstance(value_scan_target.get("sanitization"), dict):
            value_scan_target["sanitization"]["sensitive_keys_removed"] = []
        sensitive_values = self.scan_sensitive_values(value_scan_target)
        errors = []
        if forbidden_keys:
            errors.append(f"sensitive field detected in hardened evidence: {', '.join(sorted(forbidden_keys))}")
        if sensitive_values["detected"]:
            errors.append("sensitive value detected in hardened evidence")
        if any(hardened.get("forbidden", {}).values()):
            errors.append("forbidden real-action flag detected in hardened evidence")
        return {
            "valid": not errors,
            "errors": errors,
            "error_code": XHS_KJVS_DISCOVERY_SENSITIVE_FIELD_DETECTED if forbidden_keys else None,
        }

    def _find_sensitive_keys(self, value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for key, nested in value.items():
                key_text = str(key)
                if self._is_sensitive_key(key_text):
                    found.add(key_text)
                found.update(self._find_sensitive_keys(nested))
        elif isinstance(value, list):
            for item in value:
                found.update(self._find_sensitive_keys(item))
        return found

    def _extract_shops(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        shops = source.get("shops")
        if isinstance(shops, list):
            return [shop for shop in shops if isinstance(shop, dict)]
        data = source.get("data")
        if isinstance(data, dict) and isinstance(data.get("shops"), list):
            return [shop for shop in data["shops"] if isinstance(shop, dict)]
        if isinstance(data, list):
            return [shop for shop in data if isinstance(shop, dict)]
        return []

    def _build_summary(self, hardened: dict[str, Any], source_path: Path, hardened_path: str) -> dict[str, Any]:
        summary = KuaJingVSHardenedDiscoverySummary(
            status=hardened["status"],
            generated_at=self._utc_now(),
            source_evidence_path=str(source_path),
            hardened_evidence_path=hardened_path,
            shop_count=int(hardened.get("shop_count") or 0),
            safe_shop_count=sum(1 for shop in hardened.get("shops") or [] if shop.get("safe") is True),
            warning_count=len(hardened.get("warnings") or []),
            error_count=len(hardened.get("errors") or []),
            sensitive_key_removed_count=len(hardened.get("sanitization", {}).get("sensitive_keys_removed") or []),
            sensitive_value_scan_passed=bool(hardened.get("sanitization", {}).get("sensitive_value_scan_passed")),
            evidence_hash=hardened.get("evidence_hash"),
            ready_for_strict_account_binding=hardened["status"] == "success",
        )
        return self._model_to_dict(summary)

    def _is_sensitive_key(self, key: str) -> bool:
        lowered = key.lower()
        if lowered.startswith("contains_") or lowered == "sensitive_keys_removed":
            return False
        return lowered in SENSITIVE_KEYS or any(part in lowered for part in ("token", "cookie", "secret", "password", "authorization"))

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

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
