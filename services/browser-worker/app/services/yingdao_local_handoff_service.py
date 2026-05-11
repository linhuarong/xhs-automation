import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import SearchJob, WorkerResult, XhsPublishJob
from app.schemas.xhs_yingdao_handoff import (
    YingdaoEvidenceReadResult,
    YingdaoHandoffManifest,
    YingdaoHandoffResult,
    YingdaoPublishActiveJob,
    YingdaoSearchActiveJob,
)
from app.utils.errors import (
    XHS_YINGDAO_ACTIVE_JOB_INVALID,
    XHS_YINGDAO_ACTIVE_JOB_WRITE_FAILED,
    XHS_YINGDAO_EVIDENCE_INVALID,
    XHS_YINGDAO_EVIDENCE_NOT_FOUND,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class YingdaoLocalHandoffService:
    """Local JSON handoff contract for future Yingdao file-trigger RPA."""

    def __init__(self, queue_root: str | Path | None = None, worker_root: str | Path | None = None) -> None:
        """Create a local handoff service without starting Yingdao or browsers."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        root_value = queue_root or os.getenv("YINGDAO_LOCAL_QUEUE_ROOT", ".local_rpa_queue/yingdao")
        self.queue_root = self._resolve_worker_path(root_value)

    def prepare_search_handoff(self, request: SearchJob | dict[str, Any]) -> YingdaoHandoffResult:
        """Write the active search job and per-job snapshot for Yingdao."""
        payload = self._to_dict(request)
        job_id = str(payload["job_id"])
        job_dir = self.queue_root / "search" / "jobs" / job_id
        active_path = self._search_active_job_path()
        now = self._utc_now()
        active_job = YingdaoSearchActiveJob(
            job_id=job_id,
            account_id=str(payload["account_id"]),
            provider_type=str(payload.get("provider_type") or "yingdao_local_file_trigger"),
            created_at=now,
            keyword=str(payload["keyword"]),
            limit=int(payload.get("limit", 20)),
            capture_screenshot=bool(payload.get("capture_screenshot", True)),
            evidence_output_dir=str(job_dir.resolve()),
        )
        self.write_active_search_job(active_job)
        snapshot_path = self.write_job_snapshot(active_job, job_dir)
        manifest_path = self.write_handoff_manifest(active_job, job_dir)
        expected_evidence_path = job_dir / active_job.expected_evidence_file
        return YingdaoHandoffResult(
            job_id=job_id,
            status="accepted",
            message="yingdao search handoff prepared",
            active_job_path=str(active_path),
            job_dir=str(job_dir),
            manifest_path=manifest_path,
            expected_evidence_path=str(expected_evidence_path),
        )

    def prepare_publish_handoff(self, request: XhsPublishJob | dict[str, Any]) -> YingdaoHandoffResult:
        """Write the active publish job and per-job snapshot for Yingdao."""
        payload = self._to_dict(request)
        job_id = str(payload["job_id"])
        job_dir = self.queue_root / "publish" / "jobs" / job_id
        active_path = self._publish_active_job_path()
        tags = list(payload.get("tags") or [])
        image_paths = self._extract_image_paths(payload)
        now = self._utc_now()
        active_job = YingdaoPublishActiveJob(
            job_id=job_id,
            account_id=str(payload["account_id"]),
            provider_type=str(payload.get("provider_type") or "yingdao_local_file_trigger"),
            created_at=now,
            title=str(payload["title"]),
            body=str(payload.get("body") or ""),
            tags=tags,
            tags_json=json.dumps(tags, ensure_ascii=False),
            image_paths=image_paths,
            image_paths_json=json.dumps(image_paths, ensure_ascii=False),
            publish_mode=str(payload.get("publish_mode") or "manual_review"),
            evidence_output_dir=str(job_dir.resolve()),
        )
        self.write_active_publish_job(active_job)
        snapshot_path = self.write_job_snapshot(active_job, job_dir)
        manifest_path = self.write_handoff_manifest(active_job, job_dir)
        expected_evidence_path = job_dir / active_job.expected_evidence_file
        return YingdaoHandoffResult(
            job_id=job_id,
            status="accepted",
            message="yingdao publish handoff prepared",
            active_job_path=str(active_path),
            job_dir=str(job_dir),
            manifest_path=manifest_path,
            expected_evidence_path=str(expected_evidence_path),
        )

    def write_active_search_job(self, active_job: YingdaoSearchActiveJob) -> str:
        """Atomically write the active search job file."""
        return self._write_json_atomic(self._search_active_job_path(), self._model_to_dict(active_job))

    def write_active_publish_job(self, active_job: YingdaoPublishActiveJob) -> str:
        """Atomically write the active publish job file."""
        return self._write_json_atomic(self._publish_active_job_path(), self._model_to_dict(active_job))

    def write_job_snapshot(self, active_job: YingdaoSearchActiveJob | YingdaoPublishActiveJob, job_dir: str | Path) -> str:
        """Write jobs/{job_id}/job.json for repeatable handoff inspection."""
        return self._write_json_atomic(Path(job_dir) / "job.json", self._model_to_dict(active_job))

    def write_handoff_manifest(
        self,
        active_job: YingdaoSearchActiveJob | YingdaoPublishActiveJob,
        job_dir: str | Path,
    ) -> str:
        """Write a small manifest next to the job snapshot."""
        job_dir_path = Path(job_dir)
        active_path = self._search_active_job_path() if active_job.job_type == "xhs_search" else self._publish_active_job_path()
        snapshot_path = job_dir_path / "job.json"
        expected_evidence_path = job_dir_path / active_job.expected_evidence_file
        manifest = YingdaoHandoffManifest(
            job_type=active_job.job_type,
            job_id=active_job.job_id,
            active_job_path=str(active_path),
            job_snapshot_path=str(snapshot_path),
            expected_evidence_path=str(expected_evidence_path),
            created_at=active_job.created_at,
            safe_mode=active_job.safe_mode,
        )
        return self._write_json_atomic(job_dir_path / "handoff_manifest.json", self._model_to_dict(manifest))

    def read_search_evidence(self, job_id: str) -> YingdaoEvidenceReadResult:
        """Read local search evidence if Yingdao has written it."""
        return self._read_evidence(job_id=job_id, job_type="xhs_search", file_name="search_evidence.json")

    def read_publish_evidence(self, job_id: str) -> YingdaoEvidenceReadResult:
        """Read local publish evidence if Yingdao has written it."""
        return self._read_evidence(job_id=job_id, job_type="xhs_publish", file_name="publish_evidence.json")

    def convert_search_evidence_to_worker_result(self, evidence: dict[str, Any]) -> WorkerResult:
        """Convert search evidence to the browser-worker result contract."""
        return WorkerResult(
            job_id=str(evidence.get("job_id")),
            status=str(evidence.get("status") or "failed"),
            message=evidence.get("message"),
            error_code=evidence.get("error_code"),
            error_message=evidence.get("error_message"),
            screenshot_url=evidence.get("screenshot_path"),
            evidence_json_path=evidence.get("evidence_json_path"),
            items=evidence.get("items") or [],
            normalized_records=evidence.get("normalized_records") or [],
        )

    def convert_publish_evidence_to_worker_result(self, evidence: dict[str, Any]) -> WorkerResult:
        """Convert publish evidence to the browser-worker result contract."""
        return WorkerResult(
            job_id=str(evidence.get("job_id")),
            status=str(evidence.get("status") or "failed"),
            message=evidence.get("message"),
            error_code=evidence.get("error_code"),
            error_message=evidence.get("error_message"),
            screenshot_url=evidence.get("screenshot_path"),
            note_url=evidence.get("note_url"),
            evidence_json_path=evidence.get("evidence_json_path"),
            items=[],
            normalized_records=[],
        )

    def validate_evidence_schema(self, evidence: dict[str, Any], job_type: str) -> dict[str, Any]:
        """Validate the minimal local evidence shape."""
        if not isinstance(evidence, dict):
            raise WorkerError(XHS_YINGDAO_EVIDENCE_INVALID, "Yingdao evidence must be a JSON object")
        missing = [field for field in ("job_id", "status") if not evidence.get(field)]
        if missing:
            raise WorkerError(
                XHS_YINGDAO_EVIDENCE_INVALID,
                f"Yingdao evidence missing fields: {', '.join(missing)}",
            )
        evidence_job_type = evidence.get("job_type")
        if evidence_job_type and evidence_job_type != job_type:
            raise WorkerError(
                XHS_YINGDAO_EVIDENCE_INVALID,
                f"Yingdao evidence job_type mismatch: expected {job_type}, got {evidence_job_type}",
            )
        return evidence

    def get_active_job_status(self, job_type: str | None = None) -> dict[str, Any]:
        """Return shallow active job status without exposing full payloads."""
        if job_type == "search":
            return {"search": self._active_status(self._search_active_job_path())}
        if job_type == "publish":
            return {"publish": self._active_status(self._publish_active_job_path())}
        return {
            "search": self._active_status(self._search_active_job_path()),
            "publish": self._active_status(self._publish_active_job_path()),
        }

    def _read_evidence(self, job_id: str, job_type: str, file_name: str) -> YingdaoEvidenceReadResult:
        category = "search" if job_type == "xhs_search" else "publish"
        path = self.queue_root / category / "jobs" / job_id / file_name
        if not path.exists():
            return YingdaoEvidenceReadResult(
                job_id=job_id,
                job_type=job_type,
                status="waiting_rpa_result",
                message="Yingdao evidence has not been written yet",
                evidence_json_path=str(path),
                error_code=XHS_YINGDAO_EVIDENCE_NOT_FOUND,
                error_message=f"evidence not found: {path}",
            )
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
            evidence.setdefault("evidence_json_path", str(path))
            self.validate_evidence_schema(evidence, job_type)
            worker_result = (
                self.convert_search_evidence_to_worker_result(evidence)
                if job_type == "xhs_search"
                else self.convert_publish_evidence_to_worker_result(evidence)
            )
            return YingdaoEvidenceReadResult(
                job_id=job_id,
                job_type=job_type,
                status=worker_result.status,
                message=worker_result.message,
                evidence_json_path=str(path),
                evidence=evidence,
                worker_result=self._model_to_dict(worker_result),
            )
        except json.JSONDecodeError as exc:
            return YingdaoEvidenceReadResult(
                job_id=job_id,
                job_type=job_type,
                status="failed",
                evidence_json_path=str(path),
                error_code=XHS_YINGDAO_EVIDENCE_INVALID,
                error_message=f"Yingdao evidence JSON invalid: {exc}",
            )
        except WorkerError as exc:
            return YingdaoEvidenceReadResult(
                job_id=job_id,
                job_type=job_type,
                status="failed",
                evidence_json_path=str(path),
                error_code=exc.error_code,
                error_message=exc.error_message,
            )

    def _active_status(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"exists": False, "path": str(path), "job_id": None, "created_at": None, "status": "not_found"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise WorkerError(XHS_YINGDAO_ACTIVE_JOB_INVALID, "active job must be a JSON object")
            return {
                "exists": True,
                "path": str(path),
                "job_id": payload.get("job_id"),
                "created_at": payload.get("created_at"),
                "status": payload.get("status") or "unknown",
            }
        except Exception as exc:
            return {
                "exists": True,
                "path": str(path),
                "job_id": None,
                "created_at": None,
                "status": "failed",
                "error_code": XHS_YINGDAO_ACTIVE_JOB_INVALID,
                "error_message": str(exc),
            }

    def _search_active_job_path(self) -> Path:
        value = os.getenv("YINGDAO_SEARCH_ACTIVE_JOB_PATH")
        return self._resolve_worker_path(value) if value else self.queue_root / "search" / "_active_job.json"

    def _publish_active_job_path(self) -> Path:
        value = os.getenv("YINGDAO_PUBLISH_ACTIVE_JOB_PATH")
        return self._resolve_worker_path(value) if value else self.queue_root / "publish" / "_active_publish_job.json"

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_name(f"{path.name}.tmp")
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(path)
            return str(path)
        except OSError as exc:
            raise WorkerError(
                XHS_YINGDAO_ACTIVE_JOB_WRITE_FAILED,
                f"failed to write Yingdao local handoff file: {path}: {exc}",
                retryable=True,
            ) from exc

    def _extract_image_paths(self, payload: dict[str, Any]) -> list[str]:
        if "image_paths" in payload and payload.get("image_paths") is not None:
            return [str(path) for path in payload.get("image_paths") or []]
        paths = []
        for asset in payload.get("assets") or []:
            if isinstance(asset, dict) and asset.get("local_path"):
                paths.append(str(asset["local_path"]))
        return paths

    def _to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

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

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
