import hashlib
import json
import mimetypes
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from app.schemas import (
    XhsMinioStorageRequest,
    XhsMinioUploadPlan,
    XhsMinioUploadPlanItem,
    XhsMinioUploadResult,
    XhsMinioUploadResultItem,
    XhsMinioUploadSource,
    XhsMinioUploadSummary,
)
from app.utils.errors import (
    MINIO_CONFIG_MISSING,
    MINIO_OBJECT_KEY_INVALID,
    MINIO_SENSITIVE_FILE_BLOCKED,
    MINIO_SOURCE_NOT_FOUND,
    MINIO_UPLOAD_DISABLED,
    MINIO_UPLOAD_FAILED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_NAME_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(^|[\\/])\.env($|[\\/])?",
        r"(^|[\\/])\.config([\\/]|$)",
        r"credential",
        r"secret",
        r"token",
        r"cookie",
        r"api[_-]?key",
        r"password",
        r"passwd",
        r"authorization",
        r"\bauth\b",
        r"profile",
        r"localstorage",
        r"session",
        r"cache",
    )
]
SEARCH_STANDARD_SOURCES = [
    ("search_evidence.json", "evidence_json", True),
    ("normalized_evidence.json", "evidence_json", False),
    ("xhs_search_smoke.png", "screenshot", False),
    ("xhs_search_before_scroll.png", "screenshot", False),
    ("error.json", "error_json", False),
]
PUBLISH_STANDARD_SOURCES = [
    ("publish_evidence.json", "evidence_json", True),
    ("publish_before.png", "screenshot", False),
    ("publish_form_filled.png", "screenshot", False),
    ("publish_result.png", "screenshot", False),
    ("error.json", "error_json", False),
]


class MinioStorageService:
    """Controlled MinIO object storage adapter with dry-run-first behavior."""

    def __init__(
        self,
        worker_root: str | Path | None = None,
        output_root: str | Path | None = None,
        env: dict[str, str] | None = None,
        minio_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.env = env
        self.minio_client_factory = minio_client_factory
        self.output_root = self._resolve_worker_path(output_root or self._get("XHS_MINIO_STORAGE_OUTPUT_ROOT", ".local_rpa_queue/minio_storage"))

    def upload_search_artifacts(self, request: XhsMinioStorageRequest) -> XhsMinioUploadResult:
        """Plan or upload search artifacts to MinIO."""
        return self._run(request)

    def upload_publish_artifacts(self, request: XhsMinioStorageRequest) -> XhsMinioUploadResult:
        """Plan or upload publish artifacts to MinIO."""
        return self._run(request)

    def build_upload_sources_from_evidence_dir(self, job_type: str, job_id: str, evidence_dir: str | Path) -> list[XhsMinioUploadSource]:
        """Build standard source list from an evidence directory."""
        base = self._resolve_worker_path(evidence_dir)
        specs = SEARCH_STANDARD_SOURCES if self._normalize_job_type(job_type) == "search" else PUBLISH_STANDARD_SOURCES
        return [
            XhsMinioUploadSource(
                source_path=str(base / filename),
                logical_name=filename,
                artifact_type=artifact_type,
                required=required,
            )
            for filename, artifact_type, required in specs
        ]

    def build_object_key(self, job_type: str, account_id: str, job_id: str, source_path: str | Path, artifact_type: str, object_prefix: str | None = None) -> str:
        """Build sanitized object key without leaking local paths."""
        prefix = self._sanitize_segment(object_prefix or self._get("XHS_MINIO_OBJECT_PREFIX", "xhs") or "xhs")
        filename = self._sanitize_filename(Path(source_path).name)
        segments = [
            prefix,
            self._sanitize_segment(self._normalize_job_type(job_type)),
            self._sanitize_segment(account_id),
            self._sanitize_segment(job_id),
            self._sanitize_segment(artifact_type or "other"),
            filename,
        ]
        key = "/".join(segments)
        self._validate_object_key(key)
        return key

    def detect_content_type(self, path: str | Path) -> str:
        """Detect content type from filename."""
        guessed, _ = mimetypes.guess_type(str(path))
        return guessed or "application/octet-stream"

    def sha256_file(self, path: str | Path) -> str:
        """Hash a local source file."""
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    def sensitive_scan_path(self, path: str | Path) -> dict[str, Any]:
        """Block sensitive local files and directories by path/name."""
        text = str(path).replace("\\", "/")
        matches = [pattern.pattern for pattern in SENSITIVE_NAME_PATTERNS if pattern.search(text)]
        return {"passed": not matches, "matches": matches}

    def build_upload_plan(self, request: XhsMinioStorageRequest) -> XhsMinioUploadPlan:
        """Build manifest-first upload plan."""
        normalized = self._normalize_job_type(request.job_type)
        sources = request.sources
        if not sources and request.evidence_dir:
            sources = self.build_upload_sources_from_evidence_dir(normalized, request.job_id, request.evidence_dir)
        sources = sources or []
        bucket = self._get("XHS_MINIO_BUCKET", self._get("MINIO_BUCKET", "xhs-assets"))
        upload_enabled = self.get_minio_upload_enabled()
        real_upload_allowed = self.get_real_upload_allowed(request)
        items: list[XhsMinioUploadPlanItem] = []
        errors: list[WorkerError] = []
        for source in sources:
            path = self._resolve_worker_path(source.source_path)
            scan = self.sensitive_scan_path(path)
            if not scan["passed"]:
                errors.append(WorkerError(MINIO_SENSITIVE_FILE_BLOCKED, f"MinIO source path blocked by sensitive scan: {path}"))
                items.append(
                    XhsMinioUploadPlanItem(
                        source_path=str(path),
                        exists=path.exists(),
                        required=source.required,
                        artifact_type=source.artifact_type,
                        upload_allowed=False,
                        skip_reason=MINIO_SENSITIVE_FILE_BLOCKED,
                    )
                )
                continue
            exists = path.exists() and path.is_file()
            if not exists:
                if source.required:
                    errors.append(WorkerError(MINIO_SOURCE_NOT_FOUND, f"required MinIO source not found: {path}"))
                if source.required or request.include_optional_missing:
                    items.append(
                        XhsMinioUploadPlanItem(
                            source_path=str(path),
                            exists=False,
                            required=source.required,
                            artifact_type=source.artifact_type,
                            upload_allowed=False,
                            skip_reason=MINIO_SOURCE_NOT_FOUND if source.required else "optional_missing",
                        )
                    )
                continue
            object_key = self.build_object_key(normalized, request.account_id, request.job_id, path, source.artifact_type, request.object_prefix)
            items.append(
                XhsMinioUploadPlanItem(
                    source_path=str(path),
                    exists=True,
                    required=source.required,
                    artifact_type=source.artifact_type,
                    size_bytes=path.stat().st_size,
                    sha256=self.sha256_file(path),
                    object_key=object_key,
                    content_type=self.detect_content_type(path),
                    upload_allowed=real_upload_allowed,
                    skip_reason="dry_run" if request.dry_run else (None if real_upload_allowed else MINIO_UPLOAD_DISABLED),
                )
            )
        error = errors[0] if errors else None
        return XhsMinioUploadPlan(
            job_id=request.job_id,
            job_type=normalized,
            account_id=request.account_id,
            bucket=bucket,
            dry_run=request.dry_run,
            upload_enabled=upload_enabled,
            real_upload_allowed=real_upload_allowed,
            items=items,
            error_code=error.error_code if error else None,
            error_message=error.error_message if error else None,
        )

    def execute_upload_plan(self, plan: XhsMinioUploadPlan, dry_run: bool, overwrite: bool = False) -> list[XhsMinioUploadResultItem]:
        """Execute upload plan only when real upload is explicitly allowed."""
        if dry_run or not plan.real_upload_allowed:
            return [
                XhsMinioUploadResultItem(
                    source_path=item.source_path,
                    object_key=item.object_key,
                    bucket=plan.bucket,
                    uploaded=False,
                    dry_run=dry_run,
                    public_url=self._public_url(item.object_key),
                    error_code=None if item.exists and not item.skip_reason else item.skip_reason,
                    error_message=item.skip_reason,
                )
                for item in plan.items
            ]
        self._validate_upload_config()
        client = self._client()
        results: list[XhsMinioUploadResultItem] = []
        for item in plan.items:
            if not item.exists or not item.upload_allowed or not item.object_key:
                results.append(
                    XhsMinioUploadResultItem(
                        source_path=item.source_path,
                        object_key=item.object_key,
                        bucket=plan.bucket,
                        uploaded=False,
                        dry_run=False,
                        error_code=item.skip_reason,
                        error_message=item.skip_reason,
                    )
                )
                continue
            try:
                client.fput_object(
                    plan.bucket,
                    item.object_key,
                    item.source_path,
                    content_type=item.content_type or "application/octet-stream",
                )
                results.append(
                    XhsMinioUploadResultItem(
                        source_path=item.source_path,
                        object_key=item.object_key,
                        bucket=plan.bucket,
                        uploaded=True,
                        dry_run=False,
                        public_url=self._public_url(item.object_key),
                    )
                )
            except Exception as exc:
                results.append(
                    XhsMinioUploadResultItem(
                        source_path=item.source_path,
                        object_key=item.object_key,
                        bucket=plan.bucket,
                        uploaded=False,
                        dry_run=False,
                        error_code=MINIO_UPLOAD_FAILED,
                        error_message=f"MinIO upload failed: {exc}",
                    )
                )
        return results

    def write_upload_outputs(
        self,
        plan: XhsMinioUploadPlan,
        result: XhsMinioUploadResult,
        summary: XhsMinioUploadSummary,
    ) -> XhsMinioUploadResult:
        """Write plan, result, and summary JSON."""
        paths = self.get_output_paths(plan.job_id, plan.job_type)
        self._write_json(Path(paths["plan_path"]), self._model_to_dict(plan))
        self._write_json(Path(paths["result_path"]), self._model_to_dict(result))
        self._write_json(Path(paths["summary_path"]), self._model_to_dict(summary))
        return result

    def get_minio_upload_enabled(self) -> bool:
        """Return whether MinIO upload adapter is enabled."""
        return self._truthy(self._get("XHS_MINIO_UPLOAD_ENABLED", "false"))

    def get_real_upload_allowed(self, request: XhsMinioStorageRequest) -> bool:
        """Return whether real upload is allowed for this request."""
        return (
            not request.dry_run
            and self.get_minio_upload_enabled()
            and self._truthy(self._get("XHS_ALLOW_REAL_MINIO_UPLOAD", "false"))
            and self._minio_configured()
        )

    def get_output_paths(self, job_id: str, job_type: str) -> dict[str, str]:
        """Return local MinIO storage output paths."""
        normalized = self._normalize_job_type(job_type)
        output_dir = self.output_root / normalized / job_id
        return {
            "output_dir": str(output_dir),
            "plan_path": str(output_dir / "upload_plan.json"),
            "result_path": str(output_dir / "upload_result.json"),
            "summary_path": str(output_dir / "upload_summary.json"),
        }

    def _run(self, request: XhsMinioStorageRequest) -> XhsMinioUploadResult:
        normalized = self._normalize_job_type(request.job_type)
        request = request.model_copy(update={"job_type": normalized}) if hasattr(request, "model_copy") else request
        paths = self.get_output_paths(request.job_id, normalized)
        status = "success"
        error_code = None
        error_message = None
        sensitive_file_detected = False
        plan = XhsMinioUploadPlan(job_id=request.job_id, job_type=normalized, account_id=request.account_id, dry_run=request.dry_run)
        result_items: list[XhsMinioUploadResultItem] = []
        try:
            plan = self.build_upload_plan(request)
            sensitive_file_detected = any(item.skip_reason == MINIO_SENSITIVE_FILE_BLOCKED for item in plan.items)
            if plan.error_code:
                raise WorkerError(plan.error_code, plan.error_message or plan.error_code)
            if not request.dry_run and not plan.real_upload_allowed:
                raise WorkerError(MINIO_UPLOAD_DISABLED, "real MinIO upload is not explicitly enabled or configured")
            result_items = self.execute_upload_plan(plan, request.dry_run, request.overwrite)
            failed_upload = next((item for item in result_items if item.error_code == MINIO_UPLOAD_FAILED), None)
            if failed_upload:
                raise WorkerError(MINIO_UPLOAD_FAILED, failed_upload.error_message or "MinIO upload failed")
        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            if not result_items:
                result_items = [
                    XhsMinioUploadResultItem(
                        source_path=item.source_path,
                        object_key=item.object_key,
                        bucket=plan.bucket,
                        uploaded=False,
                        dry_run=request.dry_run,
                        public_url=self._public_url(item.object_key),
                        error_code=item.skip_reason,
                        error_message=item.skip_reason,
                    )
                    for item in plan.items
                ]
        uploaded_count = sum(1 for item in result_items if item.uploaded)
        skipped_count = len([item for item in result_items if not item.uploaded])
        result = XhsMinioUploadResult(
            job_id=request.job_id,
            job_type=normalized,
            account_id=request.account_id,
            status=status,
            dry_run=request.dry_run,
            bucket=plan.bucket or self._get("XHS_MINIO_BUCKET", "xhs-assets"),
            upload_enabled=plan.upload_enabled,
            real_upload_allowed=plan.real_upload_allowed,
            uploaded_count=uploaded_count,
            skipped_count=skipped_count,
            plan_path=paths["plan_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            items=result_items,
            sensitive_file_detected=sensitive_file_detected,
            error_code=error_code,
            error_message=error_message,
        )
        existing = sum(1 for item in plan.items if item.exists)
        summary = XhsMinioUploadSummary(
            job_id=request.job_id,
            job_type=normalized,
            total_sources=len(plan.items),
            existing_sources=existing,
            missing_sources=len(plan.items) - existing,
            planned_uploads=sum(1 for item in plan.items if item.exists and item.object_key),
            uploaded_count=uploaded_count,
            skipped_count=skipped_count,
            dry_run=request.dry_run,
            upload_enabled=plan.upload_enabled,
            real_upload_allowed=plan.real_upload_allowed,
            manifest_path=paths["plan_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            sensitive_scan={"passed": not sensitive_file_detected},
            created_at=self._utc_now(),
            error_code=error_code,
            error_message=error_message,
        )
        self.write_upload_outputs(plan, result, summary)
        return result

    def _client(self):
        if self.minio_client_factory:
            return self.minio_client_factory()
        try:
            from minio import Minio
        except ImportError as exc:
            raise WorkerError(MINIO_UPLOAD_FAILED, "minio package is required for real MinIO uploads") from exc
        endpoint = self._get("XHS_MINIO_ENDPOINT", self._get("MINIO_ENDPOINT", ""))
        endpoint = endpoint.replace("http://", "").replace("https://", "")
        return Minio(
            endpoint,
            access_key=self._get("XHS_MINIO_ACCESS_KEY", self._get("MINIO_ACCESS_KEY", "")),
            secret_key=self._get("XHS_MINIO_SECRET_KEY", self._get("MINIO_SECRET_KEY", "")),
            secure=self._truthy(self._get("XHS_MINIO_SECURE", "false")),
        )

    def _validate_upload_config(self) -> None:
        if not self._minio_configured():
            raise WorkerError(MINIO_CONFIG_MISSING, "MinIO endpoint, bucket, access key, and secret key are required for real upload")

    def _minio_configured(self) -> bool:
        return all(
            self._value_configured(value)
            for value in [
                self._get("XHS_MINIO_ENDPOINT", self._get("MINIO_ENDPOINT", "")),
                self._get("XHS_MINIO_BUCKET", self._get("MINIO_BUCKET", "")),
                self._get("XHS_MINIO_ACCESS_KEY", self._get("MINIO_ACCESS_KEY", "")),
                self._get("XHS_MINIO_SECRET_KEY", self._get("MINIO_SECRET_KEY", "")),
            ]
        )

    def _public_url(self, object_key: str | None) -> str | None:
        if not object_key:
            return None
        base = self._get("XHS_MINIO_PUBLIC_BASE_URL", "") or ""
        if not base:
            return None
        return f"{base.rstrip('/')}/{quote(object_key)}"

    def _validate_object_key(self, key: str) -> None:
        if not key or "\\" in key or ".." in key or re.search(r"^[A-Za-z]:", key) or "//" in key:
            raise WorkerError(MINIO_OBJECT_KEY_INVALID, f"invalid MinIO object key: {key}")
        if any(not segment for segment in key.split("/")):
            raise WorkerError(MINIO_OBJECT_KEY_INVALID, f"invalid MinIO object key: {key}")

    def _sanitize_segment(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
        if not cleaned:
            raise WorkerError(MINIO_OBJECT_KEY_INVALID, "empty MinIO object key segment")
        return cleaned[:120]

    def _sanitize_filename(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(value).name).strip(".-")
        if not cleaned:
            raise WorkerError(MINIO_OBJECT_KEY_INVALID, "empty MinIO object filename")
        return cleaned[:160]

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

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
        raise WorkerError(MINIO_OBJECT_KEY_INVALID, f"unsupported MinIO job_type: {job_type}")

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
