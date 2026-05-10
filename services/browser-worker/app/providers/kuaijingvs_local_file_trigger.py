import os
from pathlib import Path
from typing import Any

from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import STATUS_FAILED, SearchJob, WorkerResult
from app.services.kuaijingvs_service import KuaJingVSService
from app.services.local_rpa_queue import LocalRpaQueueService
from app.utils.errors import (
    KJVS_OPEN_FAILED,
    UNKNOWN_ERROR,
    WorkerError,
)


class KuaJingVSLocalFileTriggerProvider(BrowserProvider):
    """Provider that triggers Yingdao through a local pending job file."""

    provider_type = "kuaijingvs_local_file_trigger"

    def __init__(
        self,
        kuaijingvs_service: KuaJingVSService | None = None,
        queue_service: LocalRpaQueueService | None = None,
        close_after_job: bool = False,
        wait_environment_ready: bool = False,
        evidence_timeout_seconds: int | None = None,
    ) -> None:
        """Create a KuaJingVS local file trigger provider."""
        self.kuaijingvs_service = kuaijingvs_service or KuaJingVSService()
        self.queue_service = queue_service or LocalRpaQueueService()
        self.close_after_job = close_after_job
        self.wait_environment_ready = wait_environment_ready
        self.evidence_timeout_seconds = evidence_timeout_seconds or int(
            os.getenv("RPA_LOCAL_EVIDENCE_TIMEOUT_SECONDS", "300")
        )

    def search(self, job: SearchJob) -> WorkerResult:
        """Open KuaJingVS, enqueue a local RPA job, and read its evidence."""
        shop_id: str | None = None
        try:
            shop_id = self.kuaijingvs_service.resolve_shop_id(job.account_id)
            open_result = self.kuaijingvs_service.open_shop(shop_id)
            self._ensure_open_success(job.job_id, open_result)

            output_dir = self.queue_service.evidence_root / job.job_id
            output_dir.mkdir(parents=True, exist_ok=True)
            self.queue_service.enqueue_search_job(job, output_dir)
            if self.wait_environment_ready:
                self.kuaijingvs_service.wait_environment_ready(shop_id)
            evidence_path = output_dir / "search_evidence.json"
            self.queue_service.wait_for_evidence(
                evidence_path,
                timeout_seconds=self.evidence_timeout_seconds,
            )
            evidence = self.queue_service.read_evidence(evidence_path)
            return self._worker_result_from_evidence(job.job_id, evidence, evidence_path)
        except WorkerError as exc:
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=exc.error_code,
                error_message=exc.error_message,
                evidence_json_path=str(self.queue_service.evidence_root / job.job_id / "search_evidence.json"),
                items=[],
                normalized_records=[],
            )
        except Exception as exc:
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=UNKNOWN_ERROR,
                error_message=str(exc),
                evidence_json_path=str(self.queue_service.evidence_root / job.job_id / "search_evidence.json"),
                items=[],
                normalized_records=[],
            )
        finally:
            if self.close_after_job and shop_id is not None:
                try:
                    self.kuaijingvs_service.close_shop(shop_id)
                except Exception:
                    pass

    def _worker_result_from_evidence(
        self,
        job_id: str,
        evidence: dict,
        evidence_path: Path,
    ) -> WorkerResult:
        """Map local RPA evidence JSON to WorkerResult."""
        status = evidence.get("status") or STATUS_FAILED
        return WorkerResult(
            job_id=evidence.get("job_id") or job_id,
            status=status,
            message=evidence.get("message"),
            error_code=evidence.get("error_code"),
            error_message=evidence.get("error_message"),
            screenshot_url=evidence.get("screenshot_path") or evidence.get("screenshot_url"),
            note_url=evidence.get("note_url"),
            evidence_json_path=evidence.get("evidence_json_path") or str(evidence_path),
            normalized_records=evidence.get("normalized_records") or [],
            items=evidence.get("items") or [],
        )

    def _ensure_open_success(self, job_id: str, open_result: dict) -> None:
        """Raise when KuaJingVS open result is explicitly failed."""
        status = str(open_result.get("status", "")).lower() if isinstance(open_result, dict) else ""
        if status in {"failed", "error"}:
            message = open_result.get("error_message") or open_result.get("message") or status
            raise WorkerError(
                error_code=KJVS_OPEN_FAILED,
                error_message=f"KuaJingVS open failed for job {job_id}: {message}",
                retryable=True,
            )

    def open_profile(self, account_id: str) -> BrowserSession:
        """Local file trigger provider does not expose direct profile opening."""
        return BrowserSession(account_id=account_id, provider_type=self.provider_type)

    def get_driver(self, session: BrowserSession) -> Any:
        """Local file trigger provider does not expose a Selenium driver."""
        raise NotImplementedError("KuaJingVSLocalFileTriggerProvider does not expose a browser driver.")

    def check_login(self, driver: Any) -> bool:
        """Local file trigger provider does not inspect login state directly."""
        return False

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """Screenshots are expected from local RPA evidence."""
        raise NotImplementedError("KuaJingVSLocalFileTriggerProvider does not capture screenshots directly.")

    def close_profile(self, session: BrowserSession) -> None:
        """Local file trigger provider has no local browser session to close."""
        return None
