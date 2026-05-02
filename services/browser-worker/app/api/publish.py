from fastapi import APIRouter, HTTPException

from app.schemas import STATUS_ACCEPTED, PublishJob, WorkerResult
from app.services import JobStatus, job_registry


router = APIRouter(prefix="/api/xhs", tags=["xhs-publish"])


@router.post("/publish", response_model=WorkerResult)
def create_publish_job(request: PublishJob) -> WorkerResult:
    """Accept a mock XHS publish job."""
    job_registry.create_job(
        job_id=request.job_id,
        task_type="content_publish",
        status=STATUS_ACCEPTED,
    )
    return WorkerResult(
        job_id=request.job_id,
        status=STATUS_ACCEPTED,
        message="publish job accepted",
    )


@router.get("/publish/{job_id}", response_model=JobStatus)
def get_publish_job(job_id: str) -> JobStatus:
    """Return an in-memory publish job status."""
    job_status = job_registry.get_job(job_id)
    if job_status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job_status
