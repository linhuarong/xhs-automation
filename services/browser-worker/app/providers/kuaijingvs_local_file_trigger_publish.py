import os
from typing import Any

from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import STATUS_FAILED
from app.schemas.xhs_publish import XhsPublishJob, XhsPublishResult
from app.services.kuaijingvs_service import KuaJingVSService
from app.services.local_rpa_queue import LocalRpaQueueService
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService
from app.utils.errors import (
    KJVS_OPEN_FAILED,
    LOCAL_RPA_JOB_TIMEOUT,
    XHS_PUBLISH_EVIDENCE_TIMEOUT,
    WorkerError,
)


class KuaJingVSLocalFileTriggerPublishProvider(BrowserProvider):
    """Provider that triggers Yingdao publish flow through a local pending file."""

    provider_type = "kuaijingvs_local_file_trigger_publish"

    def __init__(
        self,
        kuaijingvs_service: KuaJingVSService | None = None,
        queue_service: LocalRpaQueueService | None = None,
        evidence_service: XhsPublishEvidenceService | None = None,
        close_after_job: bool = False,
        evidence_timeout_seconds: int | None = None,
    ) -> None:
        """Create a KuaJingVS local file trigger publish provider."""
        self.kuaijingvs_service = kuaijingvs_service or KuaJingVSService()
        self.queue_service = queue_service or LocalRpaQueueService()
        self.evidence_service = evidence_service or XhsPublishEvidenceService(self.queue_service.evidence_root)
        self.close_after_job = close_after_job
        self.evidence_timeout_seconds = evidence_timeout_seconds or int(
            os.getenv("RPA_LOCAL_EVIDENCE_TIMEOUT_SECONDS", "300")
        )

    def publish(self, job: XhsPublishJob) -> XhsPublishResult:
        """Open KuaJingVS, enqueue a local publish job, and read publish evidence."""
        shop_id: str | None = None
        evidence_path = self.queue_service.evidence_root / job.job_id / "publish_evidence.json"
        try:
            shop_id = self.kuaijingvs_service.resolve_shop_id(job.account_id)
            open_result = self.kuaijingvs_service.open_shop(shop_id)
            self._ensure_open_success(job.job_id, open_result)

            output_dir = self.queue_service.evidence_root / job.job_id
            output_dir.mkdir(parents=True, exist_ok=True)
            self.queue_service.enqueue_publish_job(job, output_dir)
            evidence_path = output_dir / "publish_evidence.json"
            self.queue_service.wait_for_evidence(
                evidence_path,
                timeout_seconds=self.evidence_timeout_seconds,
            )
            evidence = self.evidence_service.read_publish_evidence(evidence_path)
            return self.evidence_service.map_evidence_to_result(evidence)
        except WorkerError as exc:
            error_code = XHS_PUBLISH_EVIDENCE_TIMEOUT if exc.error_code == LOCAL_RPA_JOB_TIMEOUT else exc.error_code
            return XhsPublishResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=error_code,
                error_message=exc.error_message,
                evidence_json_path=str(evidence_path),
            )
        except Exception as exc:
            return XhsPublishResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=KJVS_OPEN_FAILED,
                error_message=str(exc),
                evidence_json_path=str(evidence_path),
            )
        finally:
            if self.close_after_job and shop_id is not None:
                try:
                    self.kuaijingvs_service.close_shop(shop_id)
                except Exception:
                    pass

    def _ensure_open_success(self, job_id: str, open_result: dict) -> None:
        """Raise when KuaJingVS open result is explicitly failed."""
        status = str(open_result.get("status", "")).lower() if isinstance(open_result, dict) else ""
        if status in {"failed", "error"}:
            message = open_result.get("error_message") or open_result.get("message") or status
            raise WorkerError(
                error_code=KJVS_OPEN_FAILED,
                error_message=f"KuaJingVS open failed for publish job {job_id}: {message}",
                retryable=True,
            )

    def open_profile(self, account_id: str) -> BrowserSession:
        """Local file trigger publish provider does not expose direct profile opening."""
        return BrowserSession(account_id=account_id, provider_type=self.provider_type)

    def get_driver(self, session: BrowserSession) -> Any:
        """Local file trigger publish provider does not expose a Selenium driver."""
        raise NotImplementedError("KuaJingVSLocalFileTriggerPublishProvider does not expose a browser driver.")

    def check_login(self, driver: Any) -> bool:
        """Local file trigger publish provider does not inspect login state directly."""
        return False

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """Screenshots are expected from local publish RPA evidence."""
        raise NotImplementedError("KuaJingVSLocalFileTriggerPublishProvider does not capture screenshots directly.")

    def close_profile(self, session: BrowserSession) -> None:
        """Local file trigger publish provider has no local browser session to close."""
        return None
