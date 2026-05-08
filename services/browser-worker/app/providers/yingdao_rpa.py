import json
from pathlib import Path
from typing import Any

from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_WAITING_HUMAN_VERIFICATION,
    SearchJob,
    WorkerResult,
)
from app.services.yingdao_service import YingdaoService


EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
YINGDAO_JOB_FAILED = "YINGDAO_JOB_FAILED"
BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
LOCAL_EVIDENCE_ROOT = BROWSER_WORKER_ROOT / ".local_evidence"


class YingdaoRpaProvider(BrowserProvider):
    """Yingdao RPA provider that reads RPA evidence JSON."""

    provider_type = "yingdao_rpa"

    def __init__(
        self,
        service: YingdaoService | None = None,
        evidence_root: str | Path | None = None,
    ) -> None:
        """Create a Yingdao RPA provider."""
        self.service = service or YingdaoService()
        self.evidence_root = Path(evidence_root) if evidence_root is not None else LOCAL_EVIDENCE_ROOT

    def search(self, job: SearchJob) -> WorkerResult:
        """Run a search RPA job and convert evidence JSON to WorkerResult."""
        output_dir = self.evidence_root / job.job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        params = [
            {"name": "job_id", "value": job.job_id},
            {"name": "account_id", "value": job.account_id},
            {"name": "keyword", "value": job.keyword},
            {"name": "limit", "value": job.limit},
            {"name": "capture_screenshot", "value": job.capture_screenshot},
            {"name": "evidence_output_dir", "value": str(output_dir)},
        ]

        try:
            start_result = self.service.start_job(
                account_name=self.service.account_name or job.account_id,
                robot_uuid=self.service.robot_uuid,
                params=params,
            )
            job_uuid = (
                start_result.get("job_uuid")
                or start_result.get("jobUuid")
                or start_result.get("uuid")
                or job.job_id
            )
            job_result = self.service.wait_job_done(str(job_uuid))
            outputs = self.service.extract_outputs(job_result)
        except Exception as exc:
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=YINGDAO_JOB_FAILED,
                error_message=str(exc),
                items=[],
                normalized_records=[],
            )

        evidence_path = self._resolve_evidence_path(outputs, output_dir)
        return self._worker_result_from_evidence(job.job_id, evidence_path)

    def _resolve_evidence_path(self, outputs: dict, output_dir: Path) -> Path:
        """Resolve the search evidence path from RPA outputs."""
        evidence_json_path = outputs.get("evidence_json_path")
        if evidence_json_path:
            return Path(str(evidence_json_path))

        output_dir_value = outputs.get("output_dir")
        if output_dir_value:
            return Path(str(output_dir_value)) / "search_evidence.json"

        return output_dir / "search_evidence.json"

    def _worker_result_from_evidence(self, job_id: str, evidence_path: Path) -> WorkerResult:
        """Read evidence JSON and map it to WorkerResult."""
        if not evidence_path.exists():
            return WorkerResult(
                job_id=job_id,
                status=STATUS_FAILED,
                error_code=EVIDENCE_NOT_FOUND,
                error_message=f"evidence not found: {evidence_path}",
                evidence_json_path=str(evidence_path),
                items=[],
                normalized_records=[],
            )

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        status = evidence.get("status") or STATUS_FAILED
        return WorkerResult(
            job_id=evidence.get("job_id") or job_id,
            status=status,
            message=evidence.get("message"),
            error_code=evidence.get("error_code"),
            error_message=evidence.get("error_message"),
            screenshot_url=evidence.get("screenshot_path") or evidence.get("screenshot_url"),
            note_url=evidence.get("note_url"),
            evidence_json_path=str(evidence_path),
            normalized_records=evidence.get("normalized_records") or [],
            items=evidence.get("items") or [],
        )

    def open_profile(self, account_id: str) -> BrowserSession:
        """RPA provider does not open browser profiles directly."""
        return BrowserSession(account_id=account_id, provider_type=self.provider_type)

    def get_driver(self, session: BrowserSession) -> Any:
        """RPA provider does not expose a Selenium driver."""
        raise NotImplementedError("YingdaoRpaProvider does not expose a browser driver.")

    def check_login(self, driver: Any) -> bool:
        """RPA provider does not inspect login state directly."""
        return False

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """RPA provider expects screenshots to be produced by Yingdao."""
        raise NotImplementedError("YingdaoRpaProvider does not capture screenshots directly.")

    def close_profile(self, session: BrowserSession) -> None:
        """RPA provider has no local browser session to close."""
        return None
