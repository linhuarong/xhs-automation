from typing import Any

from app.providers.base import BrowserProvider, BrowserSession
from app.providers.yingdao_rpa import YingdaoRpaProvider
from app.schemas import STATUS_FAILED, SearchJob, WorkerResult
from app.services.kuaijingvs_service import KuaJingVSService
from app.utils.errors import (
    KJVS_OPEN_FAILED,
    KJVS_YINGDAO_PROVIDER_ERROR,
    WorkerError,
)


class KuaJingVSYingdaoRpaProvider(BrowserProvider):
    """Provider that opens KuaJingVS environment before Yingdao RPA search."""

    provider_type = "kuaijingvs_yingdao_rpa"

    def __init__(
        self,
        kuaijingvs_service: KuaJingVSService | None = None,
        yingdao_provider: YingdaoRpaProvider | None = None,
        close_after_job: bool = False,
    ) -> None:
        """Create a KuaJingVS + Yingdao composed provider."""
        self.kuaijingvs_service = kuaijingvs_service or KuaJingVSService()
        self.yingdao_provider = yingdao_provider or YingdaoRpaProvider()
        self.close_after_job = close_after_job

    def search(self, job: SearchJob) -> WorkerResult:
        """Open KuaJingVS environment, run Yingdao search, and return its result."""
        shop_id: str | None = None
        try:
            shop_id = self.kuaijingvs_service.resolve_shop_id(job.account_id)
            open_result = self.kuaijingvs_service.open_shop(shop_id)
            self._ensure_open_success(job.job_id, open_result)
            self.kuaijingvs_service.wait_environment_ready(shop_id)
            return self.yingdao_provider.search(job)
        except WorkerError as exc:
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=exc.error_code,
                error_message=exc.error_message,
                items=[],
                normalized_records=[],
            )
        except Exception as exc:
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_FAILED,
                error_code=KJVS_YINGDAO_PROVIDER_ERROR,
                error_message=str(exc),
                items=[],
                normalized_records=[],
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
                error_message=f"KuaJingVS open failed for job {job_id}: {message}",
                retryable=True,
            )

    def open_profile(self, account_id: str) -> BrowserSession:
        """Composed RPA provider does not expose direct profile opening."""
        return BrowserSession(account_id=account_id, provider_type=self.provider_type)

    def get_driver(self, session: BrowserSession) -> Any:
        """Composed RPA provider does not expose a Selenium driver."""
        raise NotImplementedError("KuaJingVSYingdaoRpaProvider does not expose a browser driver.")

    def check_login(self, driver: Any) -> bool:
        """Composed RPA provider does not inspect login state directly."""
        return False

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """Screenshots are expected from Yingdao evidence."""
        raise NotImplementedError("KuaJingVSYingdaoRpaProvider does not capture screenshots directly.")

    def close_profile(self, session: BrowserSession) -> None:
        """Composed RPA provider has no local browser session to close."""
        return None
