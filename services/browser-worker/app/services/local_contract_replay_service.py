import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    XhsContractReplayAllResult,
    XhsContractReplayPrepareResult,
    XhsContractReplayResult,
    XhsContractReplaySummary,
    XhsN8nReplayPayload,
    XhsOpenClawReplayPayload,
)
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_CONTRACT_REPLAY_ERROR,
    XHS_CONTRACT_REPLAY_EXTERNAL_CALL_FORBIDDEN,
    XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_MISSING,
    XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_UNSAFE,
    XHS_CONTRACT_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
    XHS_CONTRACT_REPLAY_STRICT_BINDING_FAILED,
    XHS_CONTRACT_REPLAY_STRICT_BINDING_MISSING,
    XHS_CONTRACT_REPLAY_TARGET_UNSUPPORTED,
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
    "header",
    "headers",
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
LOCAL_ROUTE_BY_TARGET = {
    "n8n_mock_search_webhook": "/api/webhooks/n8n/xhs/search",
    "n8n_mock_publish_webhook": "/api/webhooks/n8n/xhs/publish",
    "openclaw_mock_job_status": "/api/webhooks/openclaw/xhs/job-status",
}


class LocalContractReplayService:
    """Replay local n8n/OpenClaw contract payloads without external calls."""

    def __init__(
        self,
        account_binding_service: XhsAccountBindingService | None = None,
        replay_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.account_binding_service = account_binding_service or XhsAccountBindingService(worker_root=self.worker_root)
        self.replay_root = self._resolve_worker_path(replay_root or os.getenv("XHS_LOCAL_CONTRACT_REPLAY_ROOT", ".local_rpa_queue/replay"))

    def prepare_n8n_search_replay(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> XhsContractReplayPrepareResult:
        """Build and replay a local n8n search contract payload."""
        request = {"job_id": job_id, "account_id": account_id, "keyword": keyword, "limit": limit}
        strict = self._load_strict_binding_result("xhs_search", job_id)
        hardened = self._load_hardened_discovery()
        payload = self.build_n8n_search_payload(strict, hardened, request)
        return self._prepare_and_replay("n8n_mock_search_webhook", "xhs_search", job_id, payload)

    def prepare_n8n_publish_replay(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> XhsContractReplayPrepareResult:
        """Build and replay a local n8n publish contract payload."""
        request = {
            "job_id": job_id,
            "account_id": account_id,
            "title": title,
            "body": body,
            "tags": tags,
            "image_paths": image_paths,
            "publish_mode": publish_mode,
        }
        strict = self._load_strict_binding_result("xhs_publish", job_id)
        hardened = self._load_hardened_discovery()
        payload = self.build_n8n_publish_payload(strict, hardened, request)
        return self._prepare_and_replay("n8n_mock_publish_webhook", "xhs_publish", job_id, payload)

    def prepare_openclaw_status_replay(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
    ) -> XhsContractReplayPrepareResult:
        """Build and replay a local OpenClaw job-status contract payload."""
        normalized = self._normalize_job_type(job_type)
        strict = self._load_strict_binding_result(normalized, job_id)
        request = {"job_id": job_id, "job_type": normalized, "account_id": account_id}
        payload = self.build_openclaw_status_payload(strict, request)
        return self._prepare_and_replay("openclaw_mock_job_status", normalized, job_id, payload)

    def build_n8n_search_payload(
        self,
        strict_binding_result: dict[str, Any],
        hardened_discovery: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Build safe local n8n search replay payload."""
        profile = strict_binding_result.get("matched_profile") or {}
        payload = XhsN8nReplayPayload(
            target="n8n_mock_search_webhook",
            job_type="xhs_search",
            job_id=request["job_id"],
            account_id=request["account_id"],
            provider_type=profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
            created_at=self._utc_now(),
            payload={
                "event": "xhs.search.requested",
                "job_id": request["job_id"],
                "account_id": request["account_id"],
                "keyword": request.get("keyword"),
                "limit": request.get("limit", 20),
                "capture_screenshot": True,
                "provider_type": profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
            },
            strict_account_binding=self._strict_binding_context(strict_binding_result),
            hardened_discovery=self._hardened_reference(hardened_discovery),
        )
        return self.sanitize_replay_payload(self._model_to_dict(payload))

    def build_n8n_publish_payload(
        self,
        strict_binding_result: dict[str, Any],
        hardened_discovery: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Build safe local n8n publish replay payload."""
        profile = strict_binding_result.get("matched_profile") or {}
        payload = XhsN8nReplayPayload(
            target="n8n_mock_publish_webhook",
            job_type="xhs_publish",
            job_id=request["job_id"],
            account_id=request["account_id"],
            provider_type=profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
            created_at=self._utc_now(),
            payload={
                "event": "xhs.publish.requested",
                "job_id": request["job_id"],
                "account_id": request["account_id"],
                "title": request.get("title"),
                "body": request.get("body"),
                "tags": request.get("tags") or [],
                "image_paths": request.get("image_paths") or [],
                "publish_mode": request.get("publish_mode") or "manual_review",
                "provider_type": profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
            },
            strict_account_binding=self._strict_binding_context(strict_binding_result),
            hardened_discovery=self._hardened_reference(hardened_discovery),
        )
        return self.sanitize_replay_payload(self._model_to_dict(payload))

    def build_openclaw_status_payload(self, strict_binding_result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        """Build safe local OpenClaw job-status replay payload."""
        profile = strict_binding_result.get("matched_profile") or {}
        shop = strict_binding_result.get("matched_shop") or {}
        payload = XhsOpenClawReplayPayload(
            job_type=request["job_type"],
            job_id=request["job_id"],
            account_id=request["account_id"],
            created_at=self._utc_now(),
            payload={
                "event": "xhs.job_status.query",
                "job_id": request["job_id"],
                "job_type": request["job_type"],
                "account_id": request["account_id"],
            },
            expected_status_context={
                "strict_binding_status": strict_binding_result.get("binding_status"),
                "provider_type": profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
                "shop_id": profile.get("shop_id") or shop.get("shop_id"),
                "shop_name": profile.get("shop_name") or shop.get("shop_name"),
                "workflow_status": "local_replay_only",
            },
        )
        return self.sanitize_replay_payload(self._model_to_dict(payload))

    def sanitize_replay_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive keyed fields before scanning/writing replay payloads."""
        sanitized = self._remove_sensitive_keys(payload)
        scan = self.scan_sensitive_payload(sanitized)
        if not scan["passed"]:
            raise WorkerError(
                XHS_CONTRACT_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
                f"replay payload contains sensitive content: {', '.join(scan['matches'])}",
            )
        return sanitized

    def scan_sensitive_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Scan payload keys and values for sensitive material."""
        matches: list[str] = []

        def visit(value: Any, path: str = "$") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    lowered = str(key).strip().lower()
                    if lowered in SENSITIVE_KEYS or any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
                        matches.append(f"{path}.{key}")
                    visit(child, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, f"{path}[{index}]")
            elif isinstance(value, str):
                if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
                    matches.append(path)

        visit(payload)
        return {"passed": not matches, "matches": matches}

    def write_replay_payload(self, target: str, job_type: str, job_id: str, payload: dict[str, Any]) -> str:
        """Write replay_payload.json."""
        return self._write_json(Path(self.get_replay_paths(target, job_type, job_id)["payload_path"]), payload)

    def replay_to_local_route(self, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Replay to an allowed browser-worker local mock route without HTTP/network."""
        if target.startswith("http://") or target.startswith("https://"):
            raise WorkerError(XHS_CONTRACT_REPLAY_EXTERNAL_CALL_FORBIDDEN, "external replay URL is forbidden")
        local_route = LOCAL_ROUTE_BY_TARGET.get(target)
        if not local_route:
            raise WorkerError(XHS_CONTRACT_REPLAY_TARGET_UNSUPPORTED, f"unsupported replay target: {target}")
        scan = self.scan_sensitive_payload(payload)
        if not scan["passed"]:
            raise WorkerError(
                XHS_CONTRACT_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
                f"replay payload contains sensitive content: {', '.join(scan['matches'])}",
            )
        return {
            "local_route": local_route,
            "http_status_code": 200,
            "response_status": "accepted" if target.startswith("n8n_") else "ok",
            "external_calls_made": False,
        }

    def write_replay_result(self, target: str, job_type: str, job_id: str, result: dict[str, Any]) -> str:
        """Write replay_result.json."""
        return self._write_json(Path(self.get_replay_paths(target, job_type, job_id)["result_path"]), result)

    def write_replay_summary(self, target: str, job_type: str, job_id: str, summary: dict[str, Any]) -> str:
        """Write replay_summary.json."""
        return self._write_json(Path(self.get_replay_paths(target, job_type, job_id)["summary_path"]), summary)

    def replay_all_for_job(self, job_id: str, job_type: str, account_id: str, payload: dict[str, Any]) -> XhsContractReplayAllResult:
        """Run strict binding plus n8n and OpenClaw local replays for one job."""
        normalized = self._normalize_job_type(job_type)
        try:
            if normalized == "xhs_search":
                strict = self.account_binding_service.prepare_search_strict_binding_check(
                    job_id=job_id,
                    account_id=account_id,
                    keyword=str(payload.get("keyword") or ""),
                    limit=int(payload.get("limit") or 20),
                )
                n8n = self.prepare_n8n_search_replay(job_id, account_id, str(payload.get("keyword") or ""), int(payload.get("limit") or 20))
            else:
                strict = self.account_binding_service.prepare_publish_strict_binding_check(
                    job_id=job_id,
                    account_id=account_id,
                    title=str(payload.get("title") or ""),
                    body=str(payload.get("body") or ""),
                    tags=list(payload.get("tags") or []),
                    image_paths=list(payload.get("image_paths") or []),
                    publish_mode=str(payload.get("publish_mode") or "manual_review"),
                )
                n8n = self.prepare_n8n_publish_replay(
                    job_id,
                    account_id,
                    str(payload.get("title") or ""),
                    str(payload.get("body") or ""),
                    list(payload.get("tags") or []),
                    list(payload.get("image_paths") or []),
                    str(payload.get("publish_mode") or "manual_review"),
                )
            openclaw = self.prepare_openclaw_status_replay(job_id, normalized, account_id)
            status = "success" if n8n.status == "success" and openclaw.status == "success" else "failed"
            return XhsContractReplayAllResult(
                job_id=job_id,
                job_type=normalized,
                status=status,
                strict_binding_status=strict.binding_status,
                n8n_replay=self._model_to_dict(n8n),
                openclaw_replay=self._model_to_dict(openclaw),
            )
        except WorkerError as exc:
            return XhsContractReplayAllResult(
                job_id=job_id,
                job_type=normalized,
                status="failed",
                error_code=exc.error_code,
                error_message=exc.error_message,
            )

    def get_replay_paths(self, target: str, job_type: str, job_id: str) -> dict[str, str]:
        """Return replay directory and file paths."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        if target == "openclaw_mock_job_status":
            replay_dir = self.replay_root / "openclaw" / "job_status" / job_id
        elif target in {"n8n_mock_search_webhook", "n8n_mock_publish_webhook"}:
            replay_dir = self.replay_root / "n8n" / category / job_id
        else:
            raise WorkerError(XHS_CONTRACT_REPLAY_TARGET_UNSUPPORTED, f"unsupported replay target: {target}")
        return {
            "replay_dir": str(replay_dir),
            "payload_path": str(replay_dir / "replay_payload.json"),
            "result_path": str(replay_dir / "replay_result.json"),
            "summary_path": str(replay_dir / "replay_summary.json"),
        }

    def _prepare_and_replay(
        self,
        target: str,
        job_type: str,
        job_id: str,
        payload: dict[str, Any],
    ) -> XhsContractReplayPrepareResult:
        normalized = self._normalize_job_type(job_type)
        paths = self.get_replay_paths(target, normalized, job_id)
        result_data: dict[str, Any] | None = None
        error_code = None
        error_message = None
        status = "success"
        payload_path = self.write_replay_payload(target, normalized, job_id, payload)
        try:
            route_result = self.replay_to_local_route(target, payload)
            result = XhsContractReplayResult(
                target=target,
                job_type=normalized,
                job_id=job_id,
                status="success",
                replayed_at=self._utc_now(),
                local_route=route_result["local_route"],
                http_status_code=route_result["http_status_code"],
                response_status=route_result["response_status"],
                strict_binding_included=bool(payload.get("strict_account_binding") or payload.get("expected_status_context")),
                strict_binding_status=self._strict_status_from_payload(payload),
                hardened_discovery_included=bool(payload.get("hardened_discovery")),
                sensitive_scan_passed=True,
                real_actions=self._real_actions_false(),
            )
            result_data = self._model_to_dict(result)
        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            result_data = self._model_to_dict(
                XhsContractReplayResult(
                    target=target,
                    job_type=normalized,
                    job_id=job_id,
                    status="failed",
                    replayed_at=self._utc_now(),
                    local_route=LOCAL_ROUTE_BY_TARGET.get(target, ""),
                    http_status_code=0,
                    response_status="failed",
                    strict_binding_included=bool(payload.get("strict_account_binding") or payload.get("expected_status_context")),
                    strict_binding_status=self._strict_status_from_payload(payload),
                    hardened_discovery_included=bool(payload.get("hardened_discovery")),
                    sensitive_scan_passed=False,
                    real_actions=self._real_actions_false(),
                    errors=[error_message],
                    error_code=error_code,
                    error_message=error_message,
                )
            )
        result_path = self.write_replay_result(target, normalized, job_id, result_data)
        summary = self._model_to_dict(
            XhsContractReplaySummary(
                target=target,
                job_type=normalized,
                job_id=job_id,
                status=status,
                payload_path=payload_path,
                result_path=result_path,
                strict_binding_status=self._strict_status_from_payload(payload),
                sensitive_scan_passed=status == "success",
                external_calls_made=False,
                ready_for_real_n8n_workflow_design=status == "success",
                ready_for_openclaw_status_design=status == "success",
                error_code=error_code,
                error_message=error_message,
            )
        )
        summary_path = self.write_replay_summary(target, normalized, job_id, summary)
        return XhsContractReplayPrepareResult(
            job_id=job_id,
            job_type=normalized,
            target=target,
            status=status,
            replay_dir=paths["replay_dir"],
            replay_payload_path=payload_path,
            replay_result_path=result_path,
            replay_summary_path=summary_path,
            local_route=LOCAL_ROUTE_BY_TARGET.get(target),
            strict_binding_status=summary.get("strict_binding_status"),
            sensitive_scan_passed=status == "success",
            external_calls_made=False,
            result=result_data,
            message="local contract replay completed without external calls" if status == "success" else "local contract replay failed safely",
            error_code=error_code,
            error_message=error_message,
        )

    def _load_strict_binding_result(self, job_type: str, job_id: str) -> dict[str, Any]:
        path = Path(self.account_binding_service.get_strict_binding_paths(job_type, job_id)["result_path"])
        if not path.exists():
            raise WorkerError(XHS_CONTRACT_REPLAY_STRICT_BINDING_MISSING, f"strict binding result not found: {path}")
        payload = self._read_json(path, XHS_CONTRACT_REPLAY_STRICT_BINDING_FAILED)
        if payload.get("status") != "success" or payload.get("binding_status") != "strict_matched":
            raise WorkerError(
                XHS_CONTRACT_REPLAY_STRICT_BINDING_FAILED,
                f"strict binding is not strict_matched: {payload.get('binding_status')}",
            )
        return payload

    def _load_hardened_discovery(self) -> dict[str, Any]:
        path = Path(self.account_binding_service.hardened_discovery_path)
        if not path.exists():
            raise WorkerError(XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_MISSING, f"hardened discovery not found: {path}")
        payload = self._read_json(path, XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_UNSAFE)
        safe = (
            payload.get("status") == "success"
            and bool((payload.get("sanitization") or {}).get("sensitive_value_scan_passed"))
            and not any((payload.get("forbidden") or {}).values())
            and not (payload.get("errors") or [])
            and bool(payload.get("evidence_hash"))
        )
        if not safe:
            raise WorkerError(XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_UNSAFE, "hardened discovery is missing safety markers or contains errors")
        return payload

    def _strict_binding_context(self, strict: dict[str, Any]) -> dict[str, Any]:
        profile = strict.get("matched_profile") or {}
        shop = strict.get("matched_shop") or {}
        return {
            "binding_status": strict.get("binding_status"),
            "strict_binding_result_path": strict.get("strict_binding_result_path"),
            "account_id": strict.get("account_id"),
            "shop_id": profile.get("shop_id") or shop.get("shop_id"),
            "shop_name": profile.get("shop_name") or shop.get("shop_name"),
            "provider_type": profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
        }

    def _hardened_reference(self, hardened: dict[str, Any]) -> dict[str, Any]:
        return {
            "hardened_discovery_path": str(self.account_binding_service.hardened_discovery_path),
            "evidence_hash": hardened.get("evidence_hash"),
            "safe": True,
        }

    def _strict_status_from_payload(self, payload: dict[str, Any]) -> str | None:
        if payload.get("strict_account_binding"):
            return (payload.get("strict_account_binding") or {}).get("binding_status")
        if payload.get("expected_status_context"):
            return (payload.get("expected_status_context") or {}).get("strict_binding_status")
        return None

    def _remove_sensitive_keys(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized = {}
            for key, child in value.items():
                lowered = str(key).strip().lower()
                if lowered in SENSITIVE_KEYS or any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
                    continue
                sanitized[key] = self._remove_sensitive_keys(child)
            return sanitized
        if isinstance(value, list):
            return [self._remove_sensitive_keys(item) for item in value]
        return value

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
            raise WorkerError(XHS_CONTRACT_REPLAY_ERROR, f"failed to write replay JSON: {path}: {exc}") from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_CONTRACT_REPLAY_ERROR, f"unsupported replay job_type: {job_type}")

    def _resolve_worker_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _real_actions_false(self) -> dict[str, bool]:
        return {
            "called_external_n8n": False,
            "called_external_openclaw": False,
            "opened_shop": False,
            "opened_xhs": False,
            "called_yingdao_openapi": False,
            "real_search_executed": False,
            "real_publish_executed": False,
        }

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
