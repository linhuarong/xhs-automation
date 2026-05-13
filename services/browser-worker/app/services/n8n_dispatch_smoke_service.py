import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    XhsFeishuReadbackRequest,
    XhsFeishuWriteRequest,
    XhsMinioStorageRequest,
    XhsMinioUploadSource,
    XhsN8nDispatchRequest,
    XhsN8nDispatchResult,
    XhsN8nDispatchStep,
    XhsN8nDispatchSummary,
)
from app.services.feishu_write_service import FeishuWriteService
from app.services.minio_storage_service import MinioStorageService
from app.services.postgres_persistence_service import PostgresPersistenceService
from app.utils.errors import (
    N8N_DISPATCH_DRY_RUN_REQUIRED,
    N8N_DISPATCH_FAILED,
    N8N_DISPATCH_NON_LOCAL_BASE_URL_BLOCKED,
    N8N_DISPATCH_SMOKE_DISABLED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
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


class N8nDispatchSmokeService:
    """Local n8n-style dry-run dispatcher for browser-worker smoke checks."""

    def __init__(
        self,
        worker_root: str | Path | None = None,
        output_root: str | Path | None = None,
        env: dict[str, str] | None = None,
        feishu_write_service: FeishuWriteService | None = None,
        minio_storage_service: MinioStorageService | None = None,
        postgres_persistence_service: PostgresPersistenceService | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.env = env
        self.output_root = self._resolve_worker_path(
            output_root or self._get("XHS_N8N_DISPATCH_OUTPUT_ROOT", ".local_rpa_queue/n8n_dispatch")
        )
        self.feishu_write_service = feishu_write_service or FeishuWriteService(worker_root=self.worker_root, env=env)
        self.minio_storage_service = minio_storage_service or MinioStorageService(worker_root=self.worker_root, env=env)
        self.postgres_persistence_service = postgres_persistence_service or PostgresPersistenceService(worker_root=self.worker_root, env=env)

    def build_n8n_webhook_payload(self, request: XhsN8nDispatchRequest) -> dict[str, Any]:
        """Build a sanitized n8n-style webhook payload for local browser-worker dispatch."""
        normalized = self._normalize_job_type(request.job_type)
        payload = {
            "schema_version": "1.0",
            "payload_type": "local_n8n_dispatch_smoke_request",
            "event": f"xhs.{normalized}.dry_run_requested" if normalized != "full" else "xhs.full_dry_run.requested",
            "job_id": request.job_id,
            "job_type": normalized,
            "account_id": request.account_id,
            "trigger_source": request.trigger_source,
            "dry_run": True,
            "base_url": request.base_url,
            "steps": self._resolve_steps(request),
            "payload": self._default_payload(request),
            "forbidden_actions": self._forbidden_actions(),
        }
        return self.sanitize_dispatch_payload(payload)

    def validate_dispatch_request(self, request: XhsN8nDispatchRequest) -> None:
        """Validate that dispatch smoke stays local and dry-run only."""
        if not request.dry_run:
            raise WorkerError(N8N_DISPATCH_DRY_RUN_REQUIRED, "n8n dispatch smoke requires dry_run=true")
        if self._truthy(self._get("XHS_N8N_DISPATCH_REQUIRE_LOCAL_BASE_URL", "true")) and not self._is_local_base_url(request.base_url):
            raise WorkerError(N8N_DISPATCH_NON_LOCAL_BASE_URL_BLOCKED, "n8n dispatch smoke BaseUrl must be localhost or 127.0.0.1")
        if self._truthy(self._get("XHS_N8N_DISPATCH_REQUIRE_ENABLED", "false")) and not self._truthy(
            self._get("XHS_N8N_DISPATCH_SMOKE_ENABLED", "false")
        ):
            raise WorkerError(N8N_DISPATCH_SMOKE_DISABLED, "n8n dispatch smoke is disabled")

    def execute_local_dry_run_dispatch(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchResult:
        """Execute local dry-run dispatch steps without real n8n or network calls."""
        request = request.model_copy(update={"job_type": self._normalize_job_type(request.job_type)})
        paths = self.get_output_paths(request.job_id, request.job_type)
        steps: list[XhsN8nDispatchStep] = []
        status = "success"
        error_code = None
        error_message = None
        sensitive_scan = {"passed": True, "matches": []}
        try:
            self.validate_dispatch_request(request)
            webhook_payload = self.build_n8n_webhook_payload(request)
            sensitive_scan = self.scan_sensitive_payload(webhook_payload)
            if not sensitive_scan["passed"]:
                raise WorkerError(N8N_DISPATCH_FAILED, f"n8n dispatch payload contains sensitive content: {sensitive_scan['matches']}")
            self._write_json(Path(paths["request_path"]), webhook_payload)
            for step_name in self._resolve_steps(request):
                steps.append(self._dispatch_step(step_name, request, paths))
            if any(step.status != "success" for step in steps):
                status = "failed"
        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            if not Path(paths["request_path"]).exists():
                self._write_json(
                    Path(paths["request_path"]),
                    {
                        "schema_version": "1.0",
                        "payload_type": "local_n8n_dispatch_smoke_request",
                        "job_id": request.job_id,
                        "job_type": request.job_type,
                        "account_id": request.account_id,
                        "dry_run": request.dry_run,
                        "safe_mode": True,
                        "input_write_limited": exc.error_code == N8N_DISPATCH_FAILED,
                        "forbidden_actions": self._forbidden_actions(),
                        "error_code": exc.error_code,
                    },
                )
        result = XhsN8nDispatchResult(
            job_id=request.job_id,
            job_type=request.job_type,
            account_id=request.account_id,
            status=status,
            trigger_source=request.trigger_source,
            dry_run=True,
            steps=steps,
            request_path=paths["request_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            external_calls_made=False,
            sensitive_payload_detected=not sensitive_scan["passed"],
            error_code=error_code,
            error_message=error_message,
        )
        summary = XhsN8nDispatchSummary(
            job_id=request.job_id,
            job_type=request.job_type,
            account_id=request.account_id,
            status=status,
            dry_run=True,
            step_count=len(steps),
            successful_step_count=sum(1 for step in steps if step.status == "success"),
            failed_step_count=sum(1 for step in steps if step.status != "success"),
            request_path=paths["request_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            generated_outputs=self._generated_outputs(paths, steps),
            forbidden_actions=self._forbidden_actions(),
            sensitive_scan=sensitive_scan,
            created_at=self._utc_now(),
            error_code=error_code,
            error_message=error_message,
        )
        self.write_n8n_dispatch_outputs(request, result, summary)
        return result

    def dispatch_step_search(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchStep:
        """Plan local search dispatch without provider execution."""
        payload = self._search_payload(request)
        return XhsN8nDispatchStep(
            step_name="search",
            status="success",
            dry_run=True,
            local_route="/api/xhs/search",
            request_payload=payload,
            response={"status": "accepted", "message": "search dry-run dispatch planned", "dry_run": True},
        )

    def dispatch_step_publish(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchStep:
        """Plan local publish dispatch without provider execution."""
        payload = self._publish_payload(request)
        return XhsN8nDispatchStep(
            step_name="publish",
            status="success",
            dry_run=True,
            local_route="/api/xhs/publish",
            request_payload=payload,
            response={"status": "accepted", "message": "publish dry-run dispatch planned", "dry_run": True},
        )

    def dispatch_step_postgres_persistence(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchStep:
        """Plan PostgreSQL dry-run dispatch without connecting to PostgreSQL."""
        payload = {
            "job_id": request.job_id,
            "account_id": request.account_id,
            "dry_run": True,
            "require_safe_payload": True,
        }
        return XhsN8nDispatchStep(
            step_name="postgres_persistence",
            status="success",
            dry_run=True,
            local_route=f"/api/workflows/xhs/postgres-persistence/{self._step_job_type(request)}",
            request_payload=payload,
            response={
                "status": "success",
                "dry_run": True,
                "rows_written": 0,
                "message": "PostgreSQL dry-run dispatch planned; no database connection attempted",
            },
        )

    def dispatch_step_minio_storage(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchStep:
        """Run controlled MinIO dry-run manifest dispatch."""
        job_type = self._step_job_type(request)
        source_path = self.get_output_paths(request.job_id, request.job_type)["request_path"]
        minio_request = XhsMinioStorageRequest(
            job_id=request.job_id,
            job_type=job_type,
            account_id=request.account_id,
            sources=[
                XhsMinioUploadSource(
                    source_path=source_path,
                    logical_name="n8n_dispatch_request.json",
                    artifact_type="manifest",
                    required=True,
                )
            ],
            dry_run=True,
            include_optional_missing=False,
            object_prefix="xhs/n8n-dispatch",
        )
        result = (
            self.minio_storage_service.upload_search_artifacts(minio_request)
            if job_type == "search"
            else self.minio_storage_service.upload_publish_artifacts(minio_request)
        )
        result_payload = self._model_to_dict(result)
        return XhsN8nDispatchStep(
            step_name="minio_storage",
            status=result.status,
            dry_run=True,
            local_route=f"/api/workflows/xhs/minio-storage/{job_type}",
            request_payload=self._model_to_dict(minio_request),
            response=result_payload,
            output_path=result.result_path,
            summary_path=result.summary_path,
            error_code=result.error_code,
            error_message=result.error_message,
        )

    def dispatch_step_feishu_write(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchStep:
        """Run controlled Feishu write dry-run dispatch."""
        job_type = self._step_job_type(request)
        write_request = XhsFeishuWriteRequest(
            job_id=request.job_id,
            job_type=job_type,
            account_id=request.account_id,
            operation="upsert_plan_only",
            records=[self._feishu_record(request, job_type)],
            dry_run=True,
        )
        result = (
            self.feishu_write_service.plan_or_write_search(write_request)
            if job_type == "search"
            else self.feishu_write_service.plan_or_write_publish(write_request)
        )
        return XhsN8nDispatchStep(
            step_name="feishu_write",
            status=result.status,
            dry_run=True,
            local_route=f"/api/workflows/xhs/feishu-write/{job_type}",
            request_payload=self._model_to_dict(write_request),
            response=self._model_to_dict(result),
            output_path=result.result_path,
            summary_path=result.summary_path,
            error_code=result.error_code,
            error_message=result.error_message,
        )

    def dispatch_step_feishu_readback(self, request: XhsN8nDispatchRequest) -> XhsN8nDispatchStep:
        """Run controlled Feishu readback dry-run planning dispatch."""
        job_type = self._step_job_type(request)
        readback_request = XhsFeishuReadbackRequest(
            job_id=request.job_id,
            job_type=job_type,
            account_id=request.account_id,
            records=[self._feishu_record(request, job_type)],
            dry_run=True,
        )
        result = (
            self.feishu_write_service.readback_search(readback_request)
            if job_type == "search"
            else self.feishu_write_service.readback_publish(readback_request)
        )
        return XhsN8nDispatchStep(
            step_name="feishu_readback",
            status=result.status,
            dry_run=True,
            local_route=f"/api/workflows/xhs/feishu-readback/{job_type}",
            request_payload=self._model_to_dict(readback_request),
            response=self._model_to_dict(result),
            output_path=result.check_path,
            summary_path=result.summary_path,
            error_code=result.error_code,
            error_message=result.error_message,
        )

    def write_n8n_dispatch_outputs(
        self,
        request: XhsN8nDispatchRequest,
        result: XhsN8nDispatchResult,
        summary: XhsN8nDispatchSummary,
    ) -> XhsN8nDispatchResult:
        """Write n8n dispatch request/result/summary JSON."""
        paths = self.get_output_paths(request.job_id, request.job_type)
        if not Path(paths["request_path"]).exists():
            self._write_json(Path(paths["request_path"]), self.build_n8n_webhook_payload(request))
        self._write_json(Path(paths["result_path"]), self._model_to_dict(result))
        self._write_json(Path(paths["summary_path"]), self._model_to_dict(summary))
        return result

    def get_output_paths(self, job_id: str, job_type: str) -> dict[str, str]:
        """Return local n8n dispatch output paths."""
        normalized = self._normalize_job_type(job_type)
        output_dir = self.output_root / normalized / job_id
        return {
            "output_dir": str(output_dir),
            "request_path": str(output_dir / "n8n_dispatch_request.json"),
            "result_path": str(output_dir / "n8n_dispatch_result.json"),
            "summary_path": str(output_dir / "n8n_dispatch_summary.json"),
        }

    def sanitize_dispatch_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Reject sensitive fields before writing dispatch payloads."""
        scan = self.scan_sensitive_payload(payload)
        if not scan["passed"]:
            raise WorkerError(N8N_DISPATCH_FAILED, f"n8n dispatch payload contains sensitive content: {scan['matches']}")
        return payload

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

    def _dispatch_step(self, step_name: str, request: XhsN8nDispatchRequest, paths: dict[str, str]) -> XhsN8nDispatchStep:
        if step_name == "full_dry_run":
            return XhsN8nDispatchStep(
                step_name="full_dry_run",
                status="success",
                dry_run=True,
                local_route="/api/workflows/xhs/n8n-dispatch/full-dry-run",
                request_payload={"job_id": request.job_id, "account_id": request.account_id, "dry_run": True},
                response={"status": "success", "dry_run": True, "output_dir": paths["output_dir"]},
            )
        dispatchers = {
            "search": self.dispatch_step_search,
            "publish": self.dispatch_step_publish,
            "postgres_persistence": self.dispatch_step_postgres_persistence,
            "minio_storage": self.dispatch_step_minio_storage,
            "feishu_write": self.dispatch_step_feishu_write,
            "feishu_readback": self.dispatch_step_feishu_readback,
        }
        return self._safe_step(dispatchers[step_name](request))

    def _resolve_steps(self, request: XhsN8nDispatchRequest) -> list[str]:
        if request.steps:
            return [str(step) for step in request.steps]
        if request.job_type == "search":
            return ["search"]
        if request.job_type == "publish":
            return ["publish"]
        return ["full_dry_run", "search", "publish", "postgres_persistence", "minio_storage", "feishu_write"]

    def _default_payload(self, request: XhsN8nDispatchRequest) -> dict[str, Any]:
        payload = dict(request.payload or {})
        payload.setdefault("job_id", request.job_id)
        payload.setdefault("account_id", request.account_id)
        payload.setdefault("dry_run", True)
        if request.job_type in {"search", "full"}:
            payload.setdefault("keyword", "XHS_SMOKE Task46")
            payload.setdefault("limit", 20)
        if request.job_type in {"publish", "full"}:
            payload.setdefault("title", "XHS_SMOKE Task46")
            payload.setdefault("body", "XHS_SMOKE Task46 dry-run publish body")
            payload.setdefault("tags", ["XHS_SMOKE", "Task46"])
            payload.setdefault("image_paths", [])
            payload.setdefault("publish_mode", "manual_review")
        return payload

    def _search_payload(self, request: XhsN8nDispatchRequest) -> dict[str, Any]:
        payload = self._default_payload(request)
        return {
            "job_id": request.job_id,
            "account_id": request.account_id,
            "keyword": payload.get("keyword") or "XHS_SMOKE Task46",
            "limit": int(payload.get("limit") or 20),
            "provider_type": "manual",
            "dry_run": True,
        }

    def _publish_payload(self, request: XhsN8nDispatchRequest) -> dict[str, Any]:
        payload = self._default_payload(request)
        return {
            "job_id": request.job_id,
            "account_id": request.account_id,
            "title": payload.get("title") or "XHS_SMOKE Task46",
            "body": payload.get("body") or "XHS_SMOKE Task46 dry-run publish body",
            "tags": list(payload.get("tags") or ["XHS_SMOKE", "Task46"]),
            "image_paths": list(payload.get("image_paths") or []),
            "publish_mode": payload.get("publish_mode") or "manual_review",
            "provider_type": "manual",
            "dry_run": True,
        }

    def _feishu_record(self, request: XhsN8nDispatchRequest, job_type: str) -> dict[str, Any]:
        payload = self._default_payload(request)
        if job_type == "search":
            return {
                "job_id": request.job_id,
                "account_id": request.account_id,
                "keyword": payload.get("keyword") or "XHS_SMOKE Task46",
                "title": "XHS_SMOKE Task46 dispatch result",
                "status": "dry_run_planned",
            }
        return {
            "job_id": request.job_id,
            "account_id": request.account_id,
            "title": payload.get("title") or "XHS_SMOKE Task46",
            "status": "XHS_SMOKE dry_run_planned",
            "body_summary": "XHS_SMOKE Task46 dry-run publish body",
        }

    def _step_job_type(self, request: XhsN8nDispatchRequest) -> str:
        return "publish" if request.job_type == "publish" else "search"

    def _generated_outputs(self, paths: dict[str, str], steps: list[XhsN8nDispatchStep]) -> list[str]:
        outputs = [paths["request_path"], paths["result_path"], paths["summary_path"]]
        for step in steps:
            outputs.extend([step.output_path, step.summary_path])
        return [path for path in outputs if path]

    def _safe_step(self, step: XhsN8nDispatchStep) -> XhsN8nDispatchStep:
        return step.model_copy(
            update={
                "request_payload": self._remove_sensitive_keys(step.request_payload),
                "response": self._remove_sensitive_keys(step.response),
            }
        )

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

    def _is_local_base_url(self, value: str) -> bool:
        return bool(re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?/?$", str(value or "").strip(), re.IGNORECASE))

    def _forbidden_actions(self) -> dict[str, bool]:
        return {
            "real_n8n_webhook": True,
            "real_feishu_write": True,
            "real_postgres_write": True,
            "real_minio_upload": True,
            "external_openclaw_call": True,
            "yingdao_openapi": True,
            "kuaijingvs_open_shop": True,
            "open_shop": True,
            "open_xhs": True,
            "open_external_webpage": True,
            "real_search": True,
            "real_publish": True,
        }

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(N8N_DISPATCH_FAILED, f"failed to write n8n dispatch JSON: {path}: {exc}") from exc

    def _resolve_worker_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "search"
        if normalized in {"publish", "xhs_publish"}:
            return "publish"
        if normalized in {"full", "full_dry_run", "all"}:
            return "full"
        raise WorkerError(N8N_DISPATCH_FAILED, f"unsupported n8n dispatch job_type: {job_type}")

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

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
