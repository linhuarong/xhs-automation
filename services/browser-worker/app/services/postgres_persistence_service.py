import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.schemas import (
    XhsPostgresPersistenceRequest,
    XhsPostgresPersistenceResult,
    XhsPostgresPersistenceSummary,
)
from app.utils.errors import (
    XHS_POSTGRES_DSN_MISSING,
    XHS_POSTGRES_INSERT_PLAN_INVALID,
    XHS_POSTGRES_PAYLOAD_INVALID,
    XHS_POSTGRES_PAYLOAD_MISSING,
    XHS_POSTGRES_PERSISTENCE_DISABLED,
    XHS_POSTGRES_PERSISTENCE_ERROR,
    XHS_POSTGRES_SCHEMA_MISSING,
    XHS_POSTGRES_SENSITIVE_PAYLOAD_DETECTED,
    XHS_POSTGRES_WRITE_FAILED,
    XHS_POSTGRES_WRITE_FORBIDDEN,
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

ALLOWED_TABLE_COLUMNS = {
    "xhs_search_evidence": {
        "job_id",
        "account_id",
        "keyword",
        "provider_type",
        "status",
        "evidence_json_path",
        "screenshot_path",
        "item_count",
        "normalized_record_count",
        "strict_binding_status",
        "hardened_discovery_status",
        "source_replay_status",
        "raw_payload",
    },
    "xhs_search_records": {
        "job_id",
        "account_id",
        "keyword",
        "rank",
        "title",
        "author",
        "published_at_text",
        "note_id",
        "note_url",
        "metric_raw_text",
        "like_count_text",
        "evidence_json_path",
        "screenshot_path",
        "raw_record",
        "captured_at",
    },
    "xhs_publish_evidence": {
        "job_id",
        "account_id",
        "title",
        "publish_mode",
        "status",
        "note_url",
        "evidence_json_path",
        "screenshot_paths",
        "image_paths",
        "strict_binding_status",
        "hardened_discovery_status",
        "source_replay_status",
        "raw_payload",
    },
    "xhs_publish_jobs": {
        "job_id",
        "account_id",
        "title",
        "body",
        "tags",
        "image_paths",
        "publish_mode",
        "status",
        "note_url",
        "error_code",
        "error_message",
        "raw_payload",
    },
    "xhs_task_log": {
        "job_id",
        "job_type",
        "account_id",
        "status",
        "source",
        "payload_path",
        "result_path",
        "raw_payload",
        "error_code",
        "error_message",
    },
    "xhs_workflow_log": {
        "run_id",
        "job_id",
        "workflow_name",
        "status",
        "input_json",
        "output_json",
        "error_code",
        "error_message",
    },
}

JSON_COLUMNS = {
    "raw_payload",
    "raw_record",
    "screenshot_paths",
    "image_paths",
    "tags",
    "input_json",
    "output_json",
}


class PostgresPersistenceService:
    """Controlled PostgreSQL phase-1 persistence from local replay payloads."""

    def __init__(
        self,
        worker_root: str | Path | None = None,
        output_root: str | Path | None = None,
        env: dict[str, str] | None = None,
        db_connect: Callable[..., Any] | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.env = env
        self.db_connect = db_connect
        self.output_root = self._resolve_worker_path(
            output_root or self._get("XHS_POSTGRES_PERSISTENCE_OUTPUT_ROOT", ".local_rpa_queue/postgres_persistence")
        )

    def persist_search_replay(self, request: XhsPostgresPersistenceRequest) -> XhsPostgresPersistenceResult:
        """Persist or dry-run a search PostgreSQL replay payload."""
        return self._persist(request)

    def persist_publish_replay(self, request: XhsPostgresPersistenceRequest) -> XhsPostgresPersistenceResult:
        """Persist or dry-run a publish PostgreSQL replay payload."""
        return self._persist(request)

    def load_persistence_payload(self, path: str | Path) -> dict[str, Any]:
        """Load Task 39 PostgreSQL mock persistence payload."""
        payload_path = self._resolve_worker_path(path)
        if not payload_path.exists():
            raise WorkerError(XHS_POSTGRES_PAYLOAD_MISSING, f"PostgreSQL persistence payload not found: {payload_path}")
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkerError(XHS_POSTGRES_PAYLOAD_INVALID, f"PostgreSQL persistence payload invalid: {payload_path}: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("persistence_type") != "local_postgres_mock_persistence":
            raise WorkerError(XHS_POSTGRES_PAYLOAD_INVALID, "PostgreSQL persistence payload must be a local_postgres_mock_persistence object")
        return payload | {"_path": str(payload_path)}

    def resolve_default_postgres_payload_path(self, job_id: str, job_type: str) -> str:
        """Resolve Task 39 postgres persistence_payload.json path."""
        normalized = self._normalize_job_type(job_type)
        return str(self.worker_root / ".local_rpa_queue" / "persistence" / "postgres" / normalized / job_id / "persistence_payload.json")

    def scan_sensitive_payload(self, payload: Any) -> dict[str, Any]:
        """Scan payload for sensitive keys or values before persistence."""
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

    def validate_postgres_write_allowed(self, dry_run: bool) -> bool:
        """Validate write flags. Dry-run never connects to PostgreSQL."""
        if dry_run:
            return False
        if not self._truthy(self._get("XHS_POSTGRES_PERSISTENCE_ENABLED", "false")):
            raise WorkerError(XHS_POSTGRES_PERSISTENCE_DISABLED, "PostgreSQL persistence is disabled")
        if not self._truthy(self._get("XHS_ALLOW_REAL_POSTGRES_WRITE", "false")):
            raise WorkerError(XHS_POSTGRES_WRITE_FORBIDDEN, "real PostgreSQL writes are not explicitly allowed")
        if not self._get("POSTGRES_DSN"):
            raise WorkerError(XHS_POSTGRES_DSN_MISSING, "POSTGRES_DSN is required for real PostgreSQL writes")
        return True

    def build_search_insert_plan(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Build insert plan for search payload rows."""
        return self._build_insert_plan(payload, "search")

    def build_publish_insert_plan(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Build insert plan for publish payload rows."""
        return self._build_insert_plan(payload, "publish")

    def apply_schema_if_allowed(self) -> str | None:
        """Apply schema only when real writes are explicitly allowed."""
        self.validate_postgres_write_allowed(dry_run=False)
        schema_path = self._resolve_worker_path(self._get("XHS_POSTGRES_SCHEMA_PATH", "database/xhs_persistence_schema.sql"))
        if not schema_path.exists():
            raise WorkerError(XHS_POSTGRES_SCHEMA_MISSING, f"PostgreSQL schema file not found: {schema_path}")
        dsn = self._get("POSTGRES_DSN")
        try:
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_path.read_text(encoding="utf-8"))
                conn.commit()
        except Exception as exc:
            raise WorkerError(XHS_POSTGRES_WRITE_FAILED, f"failed to apply PostgreSQL schema: {exc}") from exc
        return str(schema_path)

    def execute_insert_plan(self, plan: list[dict[str, Any]], dry_run: bool) -> int:
        """Execute insert plan when allowed, otherwise return zero writes."""
        if dry_run:
            return 0
        self.validate_postgres_write_allowed(dry_run=False)
        self._validate_insert_plan(plan)
        dsn = self._get("POSTGRES_DSN")
        try:
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    for item in plan:
                        columns = item["columns"]
                        placeholders = ", ".join(["%s"] * len(columns))
                        quoted_columns = ", ".join(columns)
                        values = [self._adapt_value(column, item["values"].get(column)) for column in columns]
                        cur.execute(f"INSERT INTO {item['table']} ({quoted_columns}) VALUES ({placeholders})", values)
                conn.commit()
        except Exception as exc:
            raise WorkerError(XHS_POSTGRES_WRITE_FAILED, f"failed to write PostgreSQL insert plan: {exc}") from exc
        return len(plan)

    def write_result_json(self, result: XhsPostgresPersistenceResult | dict[str, Any]) -> str:
        """Write postgres_persistence_result.json."""
        payload = self._model_to_dict(result)
        return self._write_json(Path(payload["result_path"]), payload)

    def write_summary_json(self, summary: XhsPostgresPersistenceSummary | dict[str, Any]) -> str:
        """Write postgres_persistence_summary.json."""
        payload = self._model_to_dict(summary)
        return self._write_json(Path(payload["summary_path"]), payload)

    def get_output_paths(self, job_id: str, job_type: str) -> dict[str, str]:
        """Return controlled PostgreSQL persistence output paths."""
        normalized = self._normalize_job_type(job_type)
        output_dir = self.output_root / normalized / job_id
        return {
            "output_dir": str(output_dir),
            "plan_path": str(output_dir / "postgres_persistence_plan.json"),
            "result_path": str(output_dir / "postgres_persistence_result.json"),
            "summary_path": str(output_dir / "postgres_persistence_summary.json"),
        }

    def _persist(self, request: XhsPostgresPersistenceRequest) -> XhsPostgresPersistenceResult:
        normalized = self._normalize_job_type(request.job_type)
        paths = self.get_output_paths(request.job_id, normalized)
        payload_path = request.persistence_payload_path or self.resolve_default_postgres_payload_path(request.job_id, normalized)
        status = "success"
        error_code = None
        error_message = None
        rows_written = 0
        plan: list[dict[str, Any]] = []
        scan = {"passed": True, "matches": []}
        postgres_write_enabled = False
        try:
            payload = self.load_persistence_payload(payload_path)
            scan = self.scan_sensitive_payload(payload)
            if request.require_safe_payload and not scan["passed"]:
                raise WorkerError(XHS_POSTGRES_SENSITIVE_PAYLOAD_DETECTED, f"PostgreSQL payload contains sensitive content: {scan['matches']}")
            plan = self.build_search_insert_plan(payload) if normalized == "search" else self.build_publish_insert_plan(payload)
            self._write_json(Path(paths["plan_path"]), {"schema_version": "1.0", "job_id": request.job_id, "job_type": normalized, "dry_run": request.dry_run, "plan": plan})
            postgres_write_enabled = self.validate_postgres_write_allowed(request.dry_run)
            rows_written = self.execute_insert_plan(plan, request.dry_run)
        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            if not Path(paths["plan_path"]).exists():
                self._write_json(Path(paths["plan_path"]), {"schema_version": "1.0", "job_id": request.job_id, "job_type": normalized, "dry_run": request.dry_run, "plan": plan, "error_code": exc.error_code})

        result = XhsPostgresPersistenceResult(
            job_id=request.job_id,
            job_type=normalized,
            account_id=request.account_id,
            status=status,
            dry_run=request.dry_run,
            rows_planned=len(plan),
            rows_written=rows_written,
            target_tables=sorted({item.get("table") for item in plan if item.get("table")}),
            payload_path=str(self._resolve_worker_path(payload_path)),
            plan_path=paths["plan_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            sensitive_payload_detected=not scan["passed"],
            postgres_write_enabled=postgres_write_enabled,
            error_code=error_code,
            error_message=error_message,
        )
        summary = XhsPostgresPersistenceSummary(
            job_id=request.job_id,
            job_type=normalized,
            status=status,
            dry_run=request.dry_run,
            target_tables=result.target_tables,
            rows_planned=result.rows_planned,
            rows_written=result.rows_written,
            summary_path=paths["summary_path"],
            created_at=self._utc_now(),
            payload_scan=scan,
            forbidden_actions=self._forbidden_actions(),
            error_code=error_code,
            error_message=error_message,
        )
        self.write_result_json(result)
        self.write_summary_json(summary)
        return result

    def _build_insert_plan(self, payload: dict[str, Any], job_type: str) -> list[dict[str, Any]]:
        rows = payload.get("rows") or []
        if not isinstance(rows, list):
            raise WorkerError(XHS_POSTGRES_PAYLOAD_INVALID, "PostgreSQL payload rows must be a list")
        plan: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise WorkerError(XHS_POSTGRES_PAYLOAD_INVALID, "PostgreSQL payload row must be an object")
            table = row.get("table")
            if table not in ALLOWED_TABLE_COLUMNS:
                raise WorkerError(XHS_POSTGRES_INSERT_PLAN_INVALID, f"unsupported PostgreSQL target table: {table}")
            enriched = self._enrich_row(table, row, payload, job_type)
            allowed = ALLOWED_TABLE_COLUMNS[table]
            values = {key: value for key, value in enriched.items() if key in allowed and value is not None}
            columns = [key for key in values.keys()]
            if not columns:
                raise WorkerError(XHS_POSTGRES_INSERT_PLAN_INVALID, f"no insertable columns for table: {table}")
            plan.append({"table": table, "columns": columns, "values": values})
        self._validate_insert_plan(plan)
        return plan

    def _enrich_row(self, table: str, row: dict[str, Any], payload: dict[str, Any], job_type: str) -> dict[str, Any]:
        strict = payload.get("strict_binding_context") or {}
        hardened = payload.get("hardened_discovery_reference") or {}
        replay = payload.get("source_replay_reference") or {}
        base = dict(row)
        base.setdefault("job_id", payload.get("job_id"))
        base.setdefault("account_id", payload.get("account_id"))
        base.setdefault("status", "dry_run_planned")
        base.setdefault("raw_payload", payload)
        if table in {"xhs_search_evidence", "xhs_publish_evidence"}:
            base.setdefault("provider_type", strict.get("provider_type"))
            base.setdefault("strict_binding_status", strict.get("binding_status"))
            base.setdefault("hardened_discovery_status", hardened.get("status"))
            base.setdefault("source_replay_status", replay.get("source_replay_status"))
            base.setdefault("evidence_json_path", row.get("evidence_json_path"))
        if table == "xhs_task_log":
            base.setdefault("job_type", job_type)
            base.setdefault("source", "postgres_persistence_phase_1")
            base.setdefault("payload_path", payload.get("_path"))
            base.setdefault("result_path", replay.get("result_path"))
        if table == "xhs_workflow_log":
            base.setdefault("workflow_name", row.get("workflow") or "postgres_persistence_phase_1")
            base.setdefault("status", row.get("status") or "dry_run_planned")
            base.setdefault("input_json", payload)
            base.setdefault("output_json", {"source_replay_reference": replay})
        if table == "xhs_publish_jobs":
            base.setdefault("body", None)
            base.setdefault("tags", [])
            base.setdefault("image_paths", [])
        return base

    def _validate_insert_plan(self, plan: list[dict[str, Any]]) -> None:
        if not plan:
            raise WorkerError(XHS_POSTGRES_INSERT_PLAN_INVALID, "PostgreSQL insert plan is empty")
        for item in plan:
            table = item.get("table")
            columns = item.get("columns") or []
            values = item.get("values") or {}
            if table not in ALLOWED_TABLE_COLUMNS or not columns or not isinstance(values, dict):
                raise WorkerError(XHS_POSTGRES_INSERT_PLAN_INVALID, "PostgreSQL insert plan item is invalid")
            unknown = [column for column in columns if column not in ALLOWED_TABLE_COLUMNS[table]]
            if unknown:
                raise WorkerError(XHS_POSTGRES_INSERT_PLAN_INVALID, f"unsupported columns for {table}: {unknown}")

    def _connect(self, dsn: str):
        if self.db_connect:
            return self.db_connect(dsn)
        try:
            import psycopg
        except ImportError as exc:
            raise WorkerError(XHS_POSTGRES_WRITE_FAILED, "psycopg is required for real PostgreSQL writes") from exc
        return psycopg.connect(dsn)

    def _adapt_value(self, column: str, value: Any) -> Any:
        if column not in JSON_COLUMNS:
            return value
        try:
            from psycopg.types.json import Jsonb

            return Jsonb(value)
        except Exception:
            return json.dumps(value, ensure_ascii=False)

    def _forbidden_actions(self) -> dict[str, bool]:
        return {
            "real_feishu_write": True,
            "real_minio_upload": True,
            "external_n8n_call": True,
            "external_openclaw_call": True,
            "yingdao_openapi": True,
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
            raise WorkerError(XHS_POSTGRES_PERSISTENCE_ERROR, f"failed to write PostgreSQL persistence JSON: {path}: {exc}") from exc

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
        raise WorkerError(XHS_POSTGRES_PERSISTENCE_ERROR, f"unsupported PostgreSQL persistence job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _get(self, name: str, default: str | None = None, env: dict[str, str] | None = None) -> str | None:
        source = env if env is not None else (self.env if self.env is not None else os.environ)
        value = source.get(name, default)
        return str(value).strip() if value is not None else None

    def _truthy(self, value: str | bool | None) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
