import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.utils.errors import XHS_AUDIT_LOG_ERROR, WorkerError


class AuditLogService:
    """Append local JSONL audit events for XHS workflows."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        """Create an audit log service."""
        self.log_path = self._resolve_worker_path(
            log_path or os.getenv("XHS_AUDIT_LOG_PATH", ".local_logs/xhs_audit.jsonl")
        )

    def append_event(
        self,
        event_type: str,
        job_id: str | None = None,
        batch_id: str | None = None,
        status: str | None = None,
        error_code: str | None = None,
        message: str | None = None,
        payload: dict | None = None,
        actor: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Append one audit event as UTF-8 JSONL."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "job_id": job_id,
            "batch_id": batch_id,
            "status": status,
            "error_code": error_code,
            "message": message,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "payload": payload or {},
            "actor": actor,
            "metadata": metadata or {},
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(event, ensure_ascii=False) + "\n")
            return event
        except OSError as exc:
            raise WorkerError(
                error_code=XHS_AUDIT_LOG_ERROR,
                error_message=f"failed to write XHS audit log: {self.log_path}: {exc}",
                retryable=True,
            ) from exc

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path
