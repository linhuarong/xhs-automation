import json
import os
import re
from pathlib import Path
from typing import Any

from app.schemas.xhs import XhsNormalizedRecord, XhsSearchEvidence
from app.utils.errors import (
    XHS_EVIDENCE_INVALID,
    XHS_EVIDENCE_NOT_FOUND,
    XHS_NORMALIZE_FAILED,
    WorkerError,
)


class XhsEvidenceService:
    """Read, normalize, and write XHS search evidence JSON."""

    def __init__(self, evidence_root: str | Path | None = None) -> None:
        """Create an evidence service."""
        self.evidence_root = self._resolve_worker_path(
            evidence_root or os.getenv("RPA_LOCAL_EVIDENCE_ROOT", ".local_evidence")
        )

    def read_evidence(self, path: str | Path) -> XhsSearchEvidence:
        """Read UTF-8 evidence JSON and return a compatible evidence model."""
        evidence_path = Path(path)
        try:
            raw = json.loads(evidence_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(
                error_code=XHS_EVIDENCE_NOT_FOUND,
                error_message=f"XHS evidence not found: {evidence_path}",
                retryable=False,
            ) from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(
                error_code=XHS_EVIDENCE_INVALID,
                error_message=f"XHS evidence JSON invalid: {evidence_path}: {exc}",
                retryable=False,
            ) from exc
        except OSError as exc:
            raise WorkerError(
                error_code=XHS_EVIDENCE_INVALID,
                error_message=f"failed to read XHS evidence: {evidence_path}: {exc}",
                retryable=True,
            ) from exc

        if not isinstance(raw, dict):
            raise WorkerError(
                error_code=XHS_EVIDENCE_INVALID,
                error_message=f"XHS evidence must be a JSON object: {evidence_path}",
                retryable=False,
            )
        raw.setdefault("evidence_json_path", str(evidence_path))
        return self.normalize_evidence(raw)

    def normalize_evidence(self, evidence: XhsSearchEvidence | dict) -> XhsSearchEvidence:
        """Ensure evidence has normalized records derived from items when needed."""
        try:
            model = evidence if isinstance(evidence, XhsSearchEvidence) else XhsSearchEvidence(**evidence)
            if not model.normalized_records and model.items:
                records = []
                for index, item in enumerate(model.items, start=1):
                    rank = item.rank if item.rank is not None else index
                    like_count = self.parse_count(item.like_count)
                    collect_count = self.parse_count(item.collect_count)
                    comment_count = self.parse_count(item.comment_count)
                    records.append(
                        XhsNormalizedRecord(
                            job_id=model.job_id,
                            keyword=model.keyword,
                            account_id=model.account_id,
                            provider_type=model.provider_type,
                            rank=rank,
                            title=item.title,
                            note_url=item.note_url,
                            author_name=item.author_name,
                            like_count=like_count,
                            collect_count=collect_count,
                            comment_count=comment_count,
                            engagement_score=like_count + collect_count * 1.5 + comment_count * 2,
                            evidence_json_path=model.evidence_json_path,
                            screenshot_path=model.screenshot_path,
                            captured_at=item.captured_at or model.captured_at,
                            raw=self._model_to_dict(item),
                        )
                    )
                model.normalized_records = records
            model.item_count = len(model.items)
            model.normalized_record_count = len(model.normalized_records)
            return model
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(
                error_code=XHS_NORMALIZE_FAILED,
                error_message=f"failed to normalize XHS evidence: {exc}",
                retryable=False,
            ) from exc

    def write_normalized_evidence(
        self,
        evidence: XhsSearchEvidence | dict,
        path: str | Path,
    ) -> XhsSearchEvidence:
        """Write normalized evidence JSON as UTF-8 without BOM."""
        normalized = self.normalize_evidence(evidence)
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self._model_to_dict(normalized), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return normalized

    def ensure_evidence_paths(self, job_id: str, evidence_root: str | Path | None = None) -> dict[str, Path]:
        """Return and create canonical local evidence paths for a job."""
        root = self._resolve_worker_path(evidence_root) if evidence_root is not None else self.evidence_root
        output_dir = root / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "output_dir": output_dir,
            "expected_evidence_json_path": output_dir / "search_evidence.json",
            "expected_screenshot_path": output_dir / "xhs_search_smoke.png",
            "before_scroll_screenshot_path": output_dir / "xhs_search_before_scroll.png",
        }

    def parse_count(self, value: int | float | str | None) -> int:
        """Parse XHS metric text to an integer count."""
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int | float):
            return int(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return 0
        multiplier = 1
        lower_text = text.lower()
        if lower_text.endswith("k"):
            multiplier = 1000
            text = text[:-1]
        elif text.endswith("万"):
            multiplier = 10000
            text = text[:-1]
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return 0
        try:
            return int(float(match.group(0)) * multiplier)
        except ValueError:
            return 0

    def _model_to_dict(self, value: Any) -> dict:
        """Convert Pydantic models to dictionaries across Pydantic versions."""
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
