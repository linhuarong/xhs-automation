import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.search_job import SearchJob
from app.utils.errors import (
    LOCAL_RPA_EVIDENCE_INVALID,
    LOCAL_RPA_JOB_TIMEOUT,
    LOCAL_RPA_QUEUE_ERROR,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class LocalRpaQueueService:
    """Local file queue used by Yingdao file-trigger RPA flows."""

    def __init__(
        self,
        queue_root: str | Path | None = None,
        evidence_root: str | Path | None = None,
        write_evidence_script_path: str | Path | None = None,
    ) -> None:
        """Create a local RPA queue service."""
        self.queue_root = self._resolve_worker_path(
            queue_root or os.getenv("RPA_LOCAL_QUEUE_ROOT", ".local_rpa_jobs")
        )
        self.evidence_root = self._resolve_worker_path(
            evidence_root or os.getenv("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")
        )
        self.write_evidence_script_path = self._resolve_worker_path(
            write_evidence_script_path
            or os.getenv(
                "RPA_WRITE_EVIDENCE_SCRIPT_PATH",
                "scripts/write_yingdao_smoke_evidence.ps1",
            )
        )

    def ensure_dirs(self) -> None:
        """Ensure queue state directories exist."""
        for name in ("pending", "processing", "done", "failed"):
            (self.queue_root / name).mkdir(parents=True, exist_ok=True)
        self.evidence_root.mkdir(parents=True, exist_ok=True)

    def build_search_payload(self, job: SearchJob, output_dir: str | Path) -> dict:
        """Build a UTF-8 serializable search job payload."""
        output_path = Path(output_dir)
        before_scroll_screenshot_path = output_path / "xhs_search_before_scroll.png"
        expected_screenshot_path = output_path / "xhs_search_smoke.png"
        expected_evidence_json_path = output_path / "search_evidence.json"
        return {
            "job_id": job.job_id,
            "task_type": "xhs_keyword_search",
            "account_id": job.account_id,
            "provider_type": "kuaijingvs_local_file_trigger",
            "keyword": job.keyword,
            "limit": job.limit,
            "output_dir": str(output_path),
            "before_scroll_screenshot_path": str(before_scroll_screenshot_path),
            "expected_evidence_json_path": str(expected_evidence_json_path),
            "expected_screenshot_path": str(expected_screenshot_path),
            "dos_command": self._build_dos_command(job, output_path),
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    def enqueue_search_job(self, job: SearchJob, output_dir: str | Path) -> Path:
        """Write a pending search job JSON for the local RPA trigger."""
        self.ensure_dirs()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        payload = self.build_search_payload(job, output_path)
        pending_path = self.queue_root / "pending" / f"{job.job_id}.json"
        try:
            pending_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise WorkerError(
                error_code=LOCAL_RPA_QUEUE_ERROR,
                error_message=f"failed to enqueue local RPA job: {pending_path}: {exc}",
                retryable=True,
            ) from exc
        return pending_path

    def wait_for_evidence(
        self,
        evidence_json_path: str | Path,
        timeout_seconds: int,
    ) -> Path:
        """Wait until an evidence JSON file exists."""
        evidence_path = Path(evidence_json_path)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() <= deadline:
            if evidence_path.exists():
                return evidence_path
            time.sleep(0.2)
        raise WorkerError(
            error_code=LOCAL_RPA_JOB_TIMEOUT,
            error_message=f"local RPA evidence timed out: {evidence_path}",
            retryable=True,
        )

    def read_evidence(self, evidence_json_path: str | Path) -> dict:
        """Read local RPA evidence JSON as UTF-8."""
        evidence_path = Path(evidence_json_path)
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkerError(
                error_code=LOCAL_RPA_EVIDENCE_INVALID,
                error_message=f"local RPA evidence JSON invalid: {evidence_path}: {exc}",
                retryable=False,
            ) from exc
        except OSError as exc:
            raise WorkerError(
                error_code=LOCAL_RPA_QUEUE_ERROR,
                error_message=f"failed to read local RPA evidence: {evidence_path}: {exc}",
                retryable=True,
            ) from exc
        if not isinstance(evidence, dict):
            raise WorkerError(
                error_code=LOCAL_RPA_EVIDENCE_INVALID,
                error_message=f"local RPA evidence must be a JSON object: {evidence_path}",
                retryable=False,
            )
        return evidence

    def _build_dos_command(self, job: SearchJob, output_dir: Path) -> str:
        """Build the PowerShell command exposed to Yingdao."""
        return " ".join(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy Bypass",
                "-File",
                self._quote(str(self.write_evidence_script_path)),
                "-JobId",
                self._quote(job.job_id),
                "-Keyword",
                self._quote(job.keyword),
                "-AccountId",
                self._quote(job.account_id),
                "-ProviderType",
                self._quote("kuaijingvs_local_file_trigger"),
                "-EvidenceDir",
                self._quote(str(output_dir)),
            ]
        )

    def _quote(self, value: str) -> str:
        """Quote a PowerShell command argument."""
        return f'"{value.replace(chr(34), chr(34) + chr(34))}"'

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative local RPA paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return BROWSER_WORKER_ROOT / path
