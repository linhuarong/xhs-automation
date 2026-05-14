import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib import request as urllib_request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.schemas import (
    XhsN8nHandshakePayload,
    XhsN8nHandshakeRequest,
    XhsN8nHandshakeResponse,
    XhsN8nHandshakeSummary,
)
from app.utils.errors import (
    N8N_HANDSHAKE_CONFIG_MISSING,
    N8N_HANDSHAKE_DISABLED,
    N8N_HANDSHAKE_FAILED,
    N8N_HANDSHAKE_MARKER_REQUIRED,
    N8N_HANDSHAKE_RESPONSE_INVALID,
    N8N_HANDSHAKE_WEBHOOK_URL_BLOCKED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
HANDSHAKE_MARKER = "XHS_N8N_HANDSHAKE_SMOKE"
SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "tenant_access_token",
    "user_access_token",
    "cookie",
    "set-cookie",
    "secret",
    "app_secret",
    "password",
    "passwd",
    "authorization",
    "auth",
    "api_key",
    "header",
    "headers",
    "session",
    "credential",
    "private_key",
    "table_id",
    "app_token",
    "webhook_url",
}
SENSITIVE_QUERY_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "sign",
    "signature",
    "key",
    "secret",
    "password",
    "auth",
    "authorization",
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
        r"app_secret",
    )
]


class N8nHandshakeService:
    """Controlled n8n webhook handshake smoke with dry-run-first behavior."""

    def __init__(
        self,
        worker_root: str | Path | None = None,
        output_root: str | Path | None = None,
        env: dict[str, str] | None = None,
        http_client: Callable[[str, str, dict[str, str], dict[str, Any], float], dict[str, Any]] | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.env = env
        self.http_client = http_client
        self.output_root = self._resolve_worker_path(
            output_root or self._get("XHS_N8N_HANDSHAKE_OUTPUT_ROOT", ".local_rpa_queue/n8n_handshake")
        )

    def get_n8n_handshake_enabled(self) -> bool:
        """Return whether controlled n8n handshake is enabled."""
        return self._truthy(self._get("XHS_N8N_HANDSHAKE_ENABLED", "false"))

    def get_real_n8n_handshake_allowed(self, request: XhsN8nHandshakeRequest) -> bool:
        """Return whether this request may send one real n8n handshake."""
        return (
            not request.dry_run
            and self.get_n8n_handshake_enabled()
            and self._truthy(self._get("XHS_ALLOW_REAL_N8N_HANDSHAKE", "false"))
            and bool(self._resolve_webhook_url(request))
        )

    def redact_webhook_url(self, url: str | None) -> str | None:
        """Redact secret-like URL query parameters before writing outputs."""
        if not url:
            return None
        try:
            parts = urlsplit(url)
            query = []
            for key, value in parse_qsl(parts.query, keep_blank_values=True):
                if key.lower() in SENSITIVE_QUERY_KEYS or any(sensitive in key.lower() for sensitive in SENSITIVE_QUERY_KEYS):
                    query.append((key, "REDACTED"))
                else:
                    query.append((key, value))
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
        except Exception:
            return "REDACTED_INVALID_URL"

    def validate_webhook_url(self, url: str | None, *, dry_run: bool) -> None:
        """Validate real webhook URL without requiring one for dry-run."""
        if dry_run:
            return
        if not url:
            raise WorkerError(N8N_HANDSHAKE_CONFIG_MISSING, "n8n handshake webhook URL is required for real handshake")
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            raise WorkerError(N8N_HANDSHAKE_WEBHOOK_URL_BLOCKED, "n8n handshake webhook URL must be http or https")

    def build_handshake_payload(self, request: XhsN8nHandshakeRequest) -> XhsN8nHandshakePayload:
        """Build a sanitized handshake payload."""
        normalized = self._normalize_job_type(request.job_type)
        payload = dict(request.payload or {})
        payload.setdefault("handshake_id", request.handshake_id)
        payload.setdefault("job_id", request.job_id)
        payload.setdefault("job_type", normalized)
        payload.setdefault("dry_run", request.dry_run)
        payload.setdefault("marker", request.marker)
        if request.account_id:
            payload.setdefault("account_id", request.account_id)
        handshake = XhsN8nHandshakePayload(
            event=f"xhs.n8n_handshake.{normalized}",
            handshake_id=request.handshake_id,
            job_id=request.job_id,
            job_type=normalized,
            account_id=request.account_id,
            dry_run=request.dry_run,
            marker=request.marker,
            payload=payload,
            forbidden_actions=self._forbidden_actions(),
        )
        self.validate_handshake_marker(self._model_to_dict(handshake))
        return handshake

    def validate_handshake_marker(self, payload: dict[str, Any]) -> None:
        """Validate marker presence when marker checks are enabled."""
        if self._truthy(self._get("XHS_N8N_HANDSHAKE_REQUIRE_MARKER", "true")) and HANDSHAKE_MARKER not in json.dumps(
            payload, ensure_ascii=False
        ):
            raise WorkerError(N8N_HANDSHAKE_MARKER_REQUIRED, "n8n handshake payload must contain XHS_N8N_HANDSHAKE_SMOKE marker")

    def execute_handshake(self, request: XhsN8nHandshakeRequest) -> XhsN8nHandshakeResponse:
        """Execute dry-run or one controlled real n8n webhook handshake."""
        request = request.model_copy(update={"job_type": self._normalize_job_type(request.job_type)})
        paths = self.get_output_paths(request.handshake_id, request.job_type)
        status = "success"
        error_code = None
        error_message = None
        response_body: dict[str, Any] = {}
        http_status: int | None = None
        response_valid = False
        marker_confirmed = False
        external_call_made = False
        sensitive_scan = {"passed": True, "matches": []}
        try:
            webhook_url = self._resolve_webhook_url(request)
            self.validate_webhook_url(webhook_url, dry_run=request.dry_run)
            payload = self.build_handshake_payload(request)
            payload_data = self._model_to_dict(payload)
            sensitive_scan = self.scan_sensitive_payload(payload_data)
            if not sensitive_scan["passed"]:
                raise WorkerError(N8N_HANDSHAKE_FAILED, f"n8n handshake payload contains sensitive content: {sensitive_scan['matches']}")
            request_artifact = {
                **payload_data,
                "webhook_configured": bool(webhook_url),
                "webhook_url_redacted": self.redact_webhook_url(webhook_url),
            }
            self._write_json(Path(paths["request_path"]), request_artifact)
            if request.dry_run:
                response_body = {
                    "status": "dry_run_planned",
                    "handshake_id": request.handshake_id,
                    "job_id": request.job_id,
                    "job_type": request.job_type,
                    "dry_run": True,
                    "marker": request.marker,
                }
                response_valid = True
                marker_confirmed = True
            else:
                if not self.get_n8n_handshake_enabled() or not self._truthy(self._get("XHS_ALLOW_REAL_N8N_HANDSHAKE", "false")):
                    raise WorkerError(N8N_HANDSHAKE_DISABLED, "real n8n handshake is not explicitly enabled")
                if not self.get_real_n8n_handshake_allowed(request):
                    raise WorkerError(N8N_HANDSHAKE_CONFIG_MISSING, "real n8n handshake is not fully configured")
                raw_response = self._send_handshake(webhook_url or "", payload_data)
                external_call_made = True
                http_status = int(raw_response.get("http_status") or raw_response.get("status_code") or 0)
                response_body = raw_response.get("body") if isinstance(raw_response.get("body"), dict) else raw_response
                response_body = self._remove_sensitive_keys(response_body)
                response_scan = self.scan_sensitive_payload(response_body)
                if not response_scan["passed"]:
                    raise WorkerError(
                        N8N_HANDSHAKE_RESPONSE_INVALID,
                        f"n8n handshake response contains sensitive content: {response_scan['matches']}",
                    )
                response_valid, marker_confirmed = self.validate_handshake_response(request, http_status, response_body)
                if not response_valid:
                    raise WorkerError(N8N_HANDSHAKE_RESPONSE_INVALID, "n8n handshake response did not confirm handshake_id and dry_run")
        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            if not Path(paths["request_path"]).exists():
                self._write_json(
                    Path(paths["request_path"]),
                    {
                        "schema_version": "1.0",
                        "payload_type": "controlled_n8n_handshake_smoke_request",
                        "handshake_id": request.handshake_id,
                        "job_id": request.job_id,
                        "job_type": request.job_type,
                        "dry_run": request.dry_run,
                        "safe_mode": True,
                        "webhook_url_redacted": self.redact_webhook_url(self._resolve_webhook_url(request)),
                        "input_write_limited": exc.error_code == N8N_HANDSHAKE_FAILED,
                        "forbidden_actions": self._forbidden_actions(),
                        "error_code": exc.error_code,
                    },
                )
        except Exception as exc:
            status = "failed"
            error_code = N8N_HANDSHAKE_FAILED
            error_message = f"n8n handshake failed: {exc}"

        response = XhsN8nHandshakeResponse(
            handshake_id=request.handshake_id,
            job_id=request.job_id,
            job_type=request.job_type,
            dry_run=request.dry_run,
            http_status=http_status,
            response_body=response_body,
            response_valid=response_valid and status == "success",
            marker_confirmed=marker_confirmed and status == "success",
            external_call_made=external_call_made,
            error_code=error_code,
            error_message=error_message,
        )
        summary = XhsN8nHandshakeSummary(
            handshake_id=request.handshake_id,
            job_id=request.job_id,
            job_type=request.job_type,
            dry_run=request.dry_run,
            handshake_enabled=self.get_n8n_handshake_enabled(),
            real_handshake_allowed=self.get_real_n8n_handshake_allowed(request),
            webhook_configured=bool(self._resolve_webhook_url(request)),
            webhook_url_redacted=self.redact_webhook_url(self._resolve_webhook_url(request)),
            request_path=paths["request_path"],
            response_path=paths["response_path"],
            summary_path=paths["summary_path"],
            http_status=http_status,
            response_valid=response.response_valid,
            marker_confirmed=response.marker_confirmed,
            status=status,
            sensitive_scan=sensitive_scan,
            forbidden_actions=self._forbidden_actions(),
            created_at=self._utc_now(),
            error_code=error_code,
            error_message=error_message,
        )
        self.write_handshake_outputs(request, response, summary)
        return response

    def validate_handshake_response(self, request: XhsN8nHandshakeRequest, http_status: int | None, response: dict[str, Any]) -> tuple[bool, bool]:
        """Validate HTTP status, JSON body, handshake id, dry-run flag, and marker."""
        marker_confirmed = HANDSHAKE_MARKER in json.dumps(response, ensure_ascii=False)
        if self._truthy(self._get("XHS_N8N_HANDSHAKE_REQUIRE_MARKER", "true")) and not marker_confirmed:
            return False, False
        response_valid = (
            isinstance(response, dict)
            and bool(http_status and 200 <= http_status < 300)
            and str(response.get("handshake_id")) == request.handshake_id
            and bool(response.get("dry_run")) is request.dry_run
        )
        return response_valid, marker_confirmed

    def write_handshake_outputs(
        self,
        request: XhsN8nHandshakeRequest,
        response: XhsN8nHandshakeResponse,
        summary: XhsN8nHandshakeSummary,
    ) -> XhsN8nHandshakeResponse:
        """Write request, response, and summary JSON outputs."""
        paths = self.get_output_paths(request.handshake_id, request.job_type)
        if not Path(paths["request_path"]).exists():
            payload = self._model_to_dict(self.build_handshake_payload(request))
            payload["webhook_url_redacted"] = self.redact_webhook_url(self._resolve_webhook_url(request))
            self._write_json(Path(paths["request_path"]), payload)
        self._write_json(Path(paths["response_path"]), self._model_to_dict(response))
        self._write_json(Path(paths["summary_path"]), self._model_to_dict(summary))
        return response

    def get_output_paths(self, handshake_id: str, job_type: str) -> dict[str, str]:
        """Return local n8n handshake output paths."""
        normalized = self._normalize_job_type(job_type)
        output_dir = self.output_root / normalized / handshake_id
        return {
            "output_dir": str(output_dir),
            "request_path": str(output_dir / "n8n_handshake_request.json"),
            "response_path": str(output_dir / "n8n_handshake_response.json"),
            "summary_path": str(output_dir / "n8n_handshake_summary.json"),
        }

    def scan_sensitive_payload(self, payload: Any) -> dict[str, Any]:
        """Scan payload keys and values for secret-like content."""
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
            elif isinstance(value, str) and any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
                matches.append(path)

        visit(payload)
        return {"passed": not matches, "matches": matches}

    def _send_handshake(self, webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = float(self._get("XHS_N8N_HANDSHAKE_TIMEOUT_SECONDS", "15") or "15")
        if self.http_client:
            return self.http_client("POST", webhook_url, {"Content-Type": "application/json; charset=utf-8"}, payload, timeout)
        request = urllib_request.Request(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                body_text = response.read().decode("utf-8")
                body = json.loads(body_text) if body_text else {}
                if not isinstance(body, dict):
                    raise WorkerError(N8N_HANDSHAKE_RESPONSE_INVALID, "n8n handshake response JSON must be an object")
                return {"http_status": int(response.status), "body": body}
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(N8N_HANDSHAKE_FAILED, f"n8n handshake request failed: {exc}") from exc

    def _resolve_webhook_url(self, request: XhsN8nHandshakeRequest) -> str | None:
        value = request.webhook_url or self._get("XHS_N8N_HANDSHAKE_WEBHOOK_URL")
        return value if self._value_configured(value) else None

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

    def _forbidden_actions(self) -> dict[str, bool]:
        return {
            "real_xhs_search": True,
            "real_xhs_publish": True,
            "yingdao_openapi": True,
            "kuaijingvs_open_shop": True,
            "open_shop": True,
            "open_xhs": True,
            "real_feishu_write": True,
            "real_minio_upload": True,
            "real_postgres_write": True,
            "external_openclaw_call": True,
            "batch_webhook": True,
            "retry_loop": True,
        }

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(N8N_HANDSHAKE_FAILED, f"failed to write n8n handshake JSON: {path}: {exc}") from exc

    def _resolve_worker_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"ping", "search", "publish", "full"}:
            return normalized
        raise WorkerError(N8N_HANDSHAKE_FAILED, f"unsupported n8n handshake job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _get(self, name: str, default: str | None = None) -> str | None:
        source = self.env if self.env is not None else os.environ
        value = source.get(name, default)
        return str(value).strip() if value is not None else None

    def _truthy(self, value: str | bool | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _value_configured(self, value: str | None) -> bool:
        normalized = str(value or "").strip()
        return normalized.lower() not in {"", "change_me", "changeme", "none", "null"}

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
