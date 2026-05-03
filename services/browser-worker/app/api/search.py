from fastapi import APIRouter

from app.core.xhs_search_core import search_xhs_keyword
from app.providers import SeleniumChromeProvider
from app.schemas import STATUS_ACCEPTED, SearchJob, WorkerResult
from app.services import job_registry


router = APIRouter(prefix="/api/xhs", tags=["xhs-search"])


@router.post("/search", response_model=WorkerResult)
def create_search_job(request: SearchJob) -> WorkerResult:
    """Run a minimal XHS keyword search job."""
    job_registry.create_job(
        job_id=request.job_id,
        task_type="keyword_search",
        status=STATUS_ACCEPTED,
    )
    job_registry.update_job(
        request.job_id,
        current_step="search_start",
        message="search job started",
    )

    provider = SeleniumChromeProvider()
    result = search_xhs_keyword(request, provider)
    job_registry.update_job(
        request.job_id,
        status=result.status,
        current_step="search_finished",
        message=result.message,
        error_code=result.error_code,
        error_message=result.error_message,
    )
    return result
