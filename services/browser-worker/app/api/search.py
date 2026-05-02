from fastapi import APIRouter

from app.schemas import STATUS_ACCEPTED, SearchJob, WorkerResult
from app.services import job_registry


router = APIRouter(prefix="/api/xhs", tags=["xhs-search"])


@router.post("/search", response_model=WorkerResult)
def create_search_job(request: SearchJob) -> WorkerResult:
    """Accept a mock XHS keyword search job."""
    job_registry.create_job(
        job_id=request.job_id,
        task_type="keyword_search",
        status=STATUS_ACCEPTED,
    )
    return WorkerResult(
        job_id=request.job_id,
        status=STATUS_ACCEPTED,
        message="search job accepted",
        items=[],
    )
