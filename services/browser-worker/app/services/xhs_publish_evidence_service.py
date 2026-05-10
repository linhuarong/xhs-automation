import json
import os
from pathlib import Path
from typing import Any

from app.schemas import STATUS_FAILED, STATUS_SUCCESS, STATUS_WAITING_HUMAN_VERIFICATION
from app.schemas.xhs_publish import XhsPublishEvidence, XhsPublishResult
from app.utils.errors import (
    XHS_PUBLISH_EVIDENCE_INVALID,
    XHS_PUBLISH_EVIDENCE_NOT_FOUND,
    WorkerError,
)


class XhsPublishEvidenceService:
    """Read, write, and map XHS publish evidence JSON."""

    def __init__(self, evidence_root: str | Path | None = None) -> None:
        """Create a publish evidence service."""
        self.evidence_root = self._resolve_worker_path(
            evidence_root or os.getenv("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")
        )

    def read_publish_evidence(self, path: str | Path) -> XhsPublishEvidence:
        """Read UTF-8 publish evidence JSON."""
        evidence_path = Path(path)
        try:
            raw = json.loads(evidence_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(
                error_code=XHS_PUBLISH_EVIDENCE_NOT_FOUND,
                error_message=f"XHS publish evidence not found: {evidence_path}",
                retryable=False,
            ) from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(
                error_code=XHS_PUBLISH_EVIDENCE_INVALID,
                error_message=f"XHS publish evidence JSON invalid: {evidence_path}: {exc}",
                retryable=False,
            ) from exc
        except OSError as exc:
            raise WorkerError(
                error_code=XHS_PUBLISH_EVIDENCE_INVALID,
                error_message=f"failed to read XHS publish evidence: {evidence_path}: {exc}",
                retryable=True,
            ) from exc
        if not isinstance(raw, dict):
            raise WorkerError(
                error_code=XHS_PUBLISH_EVIDENCE_INVALID,
                error_message=f"XHS publish evidence must be a JSON object: {evidence_path}",
                retryable=False,
            )
        raw.setdefault("evidence_json_path", str(evidence_path))
        return XhsPublishEvidence(**raw)

    def write_publish_evidence(
        self,
        evidence: XhsPublishEvidence | dict,
        path: str | Path,
    ) -> XhsPublishEvidence:
        """Write publish evidence JSON as UTF-8 without BOM."""
        model = evidence if isinstance(evidence, XhsPublishEvidence) else XhsPublishEvidence(**evidence)
        evidence_path = Path(path)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(self._model_to_dict(model), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return model

    def ensure_publish_paths(self, job_id: str, evidence_root: str | Path | None = None) -> dict[str, Path]:
        """Return and create canonical local publish evidence paths."""
        root = self._resolve_worker_path(evidence_root) if evidence_root is not None else self.evidence_root
        output_dir = root / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "output_dir": output_dir,
            "expected_evidence_json_path": output_dir / "publish_evidence.json",
            "before_publish_screenshot_path": output_dir / "publish_before.png",
            "form_filled_screenshot_path": output_dir / "publish_form_filled.png",
            "result_screenshot_path": output_dir / "publish_result.png",
        }

    def map_evidence_to_result(self, evidence: XhsPublishEvidence | dict) -> XhsPublishResult:
        """Map publish evidence to API result."""
        model = evidence if isinstance(evidence, XhsPublishEvidence) else XhsPublishEvidence(**evidence)
        status = model.status or STATUS_FAILED
        if status not in {STATUS_SUCCESS, STATUS_FAILED, STATUS_WAITING_HUMAN_VERIFICATION}:
            status = STATUS_FAILED
        return XhsPublishResult(
            job_id=model.job_id or "",
            status=status,
            error_code=model.error_code,
            error_message=model.error_message,
            note_url=model.note_url,
            note_id=model.note_id,
            evidence_json_path=model.evidence_json_path,
            screenshot_url=model.result_screenshot_path or model.screenshot_path,
            published_at=model.published_at,
        )

    def _model_to_dict(self, value: Any) -> dict:
        """Convert Pydantic models to dictionaries across versions."""
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _resolve_worker_path(self, value: str | Path) -> Path:
        """Resolve relative paths from services/browser-worker."""
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path
