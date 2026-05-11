import json
import os
import shutil
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from app.utils.errors import (
    MINIO_ADAPTER_NOT_CONFIGURED,
    XHS_PUBLISH_STORAGE_ARCHIVE_FAILED,
    XHS_STORAGE_ARCHIVE_FAILED,
    WorkerError,
)


class StorageAdapter(ABC):
    """Storage adapter boundary for XHS evidence archives."""

    @abstractmethod
    def archive_file(self, source_path: Path, target_path: Path) -> dict:
        """Archive one file and return a manifest entry."""


class LocalStorageAdapter(StorageAdapter):
    """Local filesystem archive adapter for tests and dry-runs."""

    def archive_file(self, source_path: Path, target_path: Path) -> dict:
        """Copy one file locally when it exists."""
        entry = {
            "source_path": str(source_path),
            "archive_path": str(target_path),
            "status": "missing",
        }
        if not source_path.exists():
            return entry
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        entry["status"] = "archived"
        return entry


class MinioStorageAdapter(StorageAdapter):
    """MinIO adapter placeholder. Real MinIO upload is intentionally out of scope."""

    def archive_file(self, source_path: Path, target_path: Path) -> dict:
        """Raise until a real MinIO adapter is configured."""
        raise WorkerError(
            error_code=MINIO_ADAPTER_NOT_CONFIGURED,
            error_message="MinIO storage adapter is not configured.",
            retryable=False,
        )


class XhsStorageService:
    """Archive local XHS evidence files into a mock local archive."""

    def __init__(
        self,
        evidence_root: str | Path | None = None,
        archive_root: str | Path | None = None,
        adapter: StorageAdapter | None = None,
    ) -> None:
        """Create an XHS storage service."""
        self.evidence_root = self._resolve_worker_path(
            evidence_root or os.getenv("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")
        )
        self.archive_root = self._resolve_worker_path(
            archive_root or os.getenv("XHS_LOCAL_ARCHIVE_ROOT", ".local_archive")
        )
        self.adapter = adapter or LocalStorageAdapter()

    def archive_evidence(self, job_id: str) -> dict:
        """Archive evidence JSON and known screenshot files, then write a manifest."""
        source_dir = self.evidence_root / job_id
        archive_dir = self.archive_root / "xhs" / job_id
        files = {
            "evidence_json_path": "search_evidence.json",
            "screenshot_path": "xhs_search_smoke.png",
            "before_scroll_screenshot_path": "xhs_search_before_scroll.png",
        }
        try:
            entries = []
            manifest = {
                "job_id": job_id,
                "evidence_json_path": str(archive_dir / files["evidence_json_path"]),
                "screenshot_path": str(archive_dir / files["screenshot_path"]),
                "before_scroll_screenshot_path": str(archive_dir / files["before_scroll_screenshot_path"]),
                "archived_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "files": entries,
            }
            for logical_name, filename in files.items():
                entry = self.adapter.archive_file(source_dir / filename, archive_dir / filename)
                entry["name"] = logical_name
                entries.append(entry)
            archive_dir.mkdir(parents=True, exist_ok=True)
            (archive_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return manifest
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(
                error_code=XHS_STORAGE_ARCHIVE_FAILED,
                error_message=f"failed to archive XHS evidence for {job_id}: {exc}",
                retryable=True,
            ) from exc

    def archive_publish_evidence(self, job_id: str) -> dict:
        """Archive publish evidence JSON and known screenshot files."""
        source_dir = self.evidence_root / job_id
        archive_dir = self.archive_root / "xhs_publish" / job_id
        files = {
            "evidence_json_path": "publish_evidence.json",
            "before_publish_screenshot_path": "publish_before.png",
            "form_filled_screenshot_path": "publish_form_filled.png",
            "result_screenshot_path": "publish_result.png",
        }
        try:
            entries = []
            manifest = {
                "job_id": job_id,
                "evidence_json_path": str(archive_dir / files["evidence_json_path"]),
                "before_publish_screenshot_path": str(archive_dir / files["before_publish_screenshot_path"]),
                "form_filled_screenshot_path": str(archive_dir / files["form_filled_screenshot_path"]),
                "result_screenshot_path": str(archive_dir / files["result_screenshot_path"]),
                "archived_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "files": entries,
            }
            for logical_name, filename in files.items():
                entry = self.adapter.archive_file(source_dir / filename, archive_dir / filename)
                entry["name"] = logical_name
                entries.append(entry)
            archive_dir.mkdir(parents=True, exist_ok=True)
            (archive_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return manifest
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(
                error_code=XHS_PUBLISH_STORAGE_ARCHIVE_FAILED,
                error_message=f"failed to archive XHS publish evidence for {job_id}: {exc}",
                retryable=True,
            ) from exc

    def archive_workflow_manifest(self, workflow_id: str, manifest: dict) -> dict:
        """Archive a mock workflow manifest locally."""
        archive_dir = self.archive_root / "xhs_workflow" / workflow_id
        archive_path = archive_dir / "manifest.json"
        payload = {
            "workflow_id": workflow_id,
            "archived_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            **manifest,
        }
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {
                "workflow_id": workflow_id,
                "manifest_path": str(archive_path),
                "status": "archived",
                "payload": payload,
            }
        except OSError as exc:
            raise WorkerError(
                error_code=XHS_STORAGE_ARCHIVE_FAILED,
                error_message=f"failed to archive XHS workflow manifest for {workflow_id}: {exc}",
                retryable=True,
            ) from exc

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path
