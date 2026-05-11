from typing import Any

from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import SearchJob, WorkerResult, XhsPublishJob
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import XHS_YINGDAO_REAL_API_DISABLED


class YingdaoLocalFileTriggerProvider(BrowserProvider):
    """Local file handoff provider for Yingdao contract tests."""

    provider_type = "yingdao_local_file_trigger"

    def __init__(self, handoff_service: YingdaoLocalHandoffService | None = None) -> None:
        """Create the provider without connecting to real Yingdao."""
        self.handoff_service = handoff_service or YingdaoLocalHandoffService()

    def prepare_search(self, job: SearchJob | dict) -> WorkerResult:
        """Prepare a local search handoff and return accepted status."""
        result = self.handoff_service.prepare_search_handoff(job)
        return WorkerResult(
            job_id=result.job_id,
            status=result.status,
            message=result.message,
            evidence_json_path=result.expected_evidence_path,
        )

    def prepare_publish(self, job: XhsPublishJob | dict) -> WorkerResult:
        """Prepare a local publish handoff and return accepted status."""
        result = self.handoff_service.prepare_publish_handoff(job)
        return WorkerResult(
            job_id=result.job_id,
            status=result.status,
            message=result.message,
            evidence_json_path=result.expected_evidence_path,
        )

    def read_search_result(self, job_id: str) -> WorkerResult:
        """Read search evidence if it exists."""
        read_result = self.handoff_service.read_search_evidence(job_id)
        if read_result.worker_result:
            return WorkerResult(**read_result.worker_result)
        return WorkerResult(
            job_id=job_id,
            status=read_result.status,
            message=read_result.message,
            error_code=read_result.error_code,
            error_message=read_result.error_message,
            evidence_json_path=read_result.evidence_json_path,
        )

    def read_publish_result(self, job_id: str) -> WorkerResult:
        """Read publish evidence if it exists."""
        read_result = self.handoff_service.read_publish_evidence(job_id)
        if read_result.worker_result:
            return WorkerResult(**read_result.worker_result)
        return WorkerResult(
            job_id=job_id,
            status=read_result.status,
            message=read_result.message,
            error_code=read_result.error_code,
            error_message=read_result.error_message,
            evidence_json_path=read_result.evidence_json_path,
        )

    def open_profile(self, account_id: str) -> BrowserSession:
        """This provider never opens a real browser profile."""
        raise NotImplementedError(XHS_YINGDAO_REAL_API_DISABLED)

    def get_driver(self, session: BrowserSession) -> Any:
        """This provider never exposes a browser driver."""
        raise NotImplementedError(XHS_YINGDAO_REAL_API_DISABLED)

    def check_login(self, driver: Any) -> bool:
        """This provider never checks real browser login state."""
        raise NotImplementedError(XHS_YINGDAO_REAL_API_DISABLED)

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """This provider never captures real browser screenshots."""
        raise NotImplementedError(XHS_YINGDAO_REAL_API_DISABLED)

    def close_profile(self, session: BrowserSession) -> None:
        """No real session is opened by this provider."""
        return None
