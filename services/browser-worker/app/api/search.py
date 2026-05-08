from fastapi import APIRouter

from app.core.xhs_search_core import search_xhs_keyword
from app.providers import get_provider
from app.schemas import (
    STATUS_ACCEPTED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_WAITING_HUMAN_VERIFICATION,
    SearchJob,
    WorkerResult,
)
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

    provider = get_provider(request.provider_type)
    search = getattr(provider, "search", None)
    if callable(search):
        result = search(request)
    else:
        result = search_xhs_keyword(request, provider)
    current_step = {
        STATUS_SUCCESS: "search_success",
        STATUS_FAILED: "search_failed",
        STATUS_WAITING_HUMAN_VERIFICATION: "waiting_human_verification",
    }.get(result.status, "search_finished")
    job_registry.update_job(
        request.job_id,
        status=result.status,
        current_step=current_step,
        message=result.message,
        error_code=result.error_code,
        error_message=result.error_message,
    )
    return result
