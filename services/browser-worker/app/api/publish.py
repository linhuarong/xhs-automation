from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.providers import get_provider
from app.schemas import (
    STATUS_ACCEPTED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    XhsBatchPublishRequest,
    XhsBatchPublishResult,
    XhsPublishJob,
    XhsPublishResult,
)
from app.services import JobStatus, job_registry
from app.services.local_rpa_queue import LocalRpaQueueService
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService
from app.utils.errors import (
    XHS_PUBLISH_BATCH_FAILED,
    XHS_PUBLISH_BATCH_PARTIAL_FAILED,
    XHS_PUBLISH_EVIDENCE_NOT_FOUND,
    XHS_PUBLISH_FAILED,
    XHS_PUBLISH_JOB_NOT_FOUND,
    WorkerError,
)


router = APIRouter(prefix="/api/xhs", tags=["xhs-publish"])
publish_evidence_service = XhsPublishEvidenceService()
local_rpa_queue_service = LocalRpaQueueService()


@router.post("/publish", response_model=XhsPublishResult)
def create_publish_job(request: XhsPublishJob) -> XhsPublishResult:
    """Run a local-file-trigger XHS publish job."""
    job_registry.create_job(
        job_id=request.job_id,
        task_type="content_publish",
        status=STATUS_ACCEPTED,
    )
    provider = get_provider(request.provider_type)
    publish = getattr(provider, "publish", None)
    if not callable(publish):
        result = XhsPublishResult(
            job_id=request.job_id,
            status=STATUS_FAILED,
            error_code=XHS_PUBLISH_FAILED,
            error_message=f"provider does not support publish: {request.provider_type}",
        )
    else:
        result = publish(request)
    job_registry.update_job(
        request.job_id,
        status=result.status,
        current_step="publish_finished",
        error_code=result.error_code,
        error_message=result.error_message,
        message=result.message,
    )
    return result


@router.post("/publish/batch", response_model=XhsBatchPublishResult)
def create_publish_batch(request: XhsBatchPublishRequest) -> XhsBatchPublishResult:
    """Run a sync batch of local publish jobs."""
    created_at = _utc_now_iso()
    jobs: list[dict] = []
    if request.mode != "sync":
        return XhsBatchPublishResult(
            batch_id=request.batch_id,
            status=STATUS_FAILED,
            total_jobs=len(request.jobs),
            success_count=0,
            failed_count=len(request.jobs),
            jobs=[],
            created_at=created_at,
            finished_at=_utc_now_iso(),
        )
    try:
        provider = get_provider(request.provider_type)
        publish = getattr(provider, "publish", None)
        if not callable(publish):
            raise WorkerError(
                error_code=XHS_PUBLISH_BATCH_FAILED,
                error_message=f"provider does not support publish: {request.provider_type}",
                retryable=False,
            )
        for job in request.jobs:
            payload = _model_to_dict(job)
            payload["account_id"] = payload.get("account_id") or request.account_id
            payload["provider_type"] = request.provider_type
            publish_job = XhsPublishJob(**payload)
            try:
                result = publish(publish_job)
            except WorkerError as exc:
                result = XhsPublishResult(
                    job_id=publish_job.job_id,
                    status=STATUS_FAILED,
                    error_code=exc.error_code,
                    error_message=exc.error_message,
                )
            except Exception as exc:
                result = XhsPublishResult(
                    job_id=publish_job.job_id,
                    status=STATUS_FAILED,
                    error_code=XHS_PUBLISH_FAILED,
                    error_message=str(exc),
                )
            jobs.append(
                {
                    "job_id": result.job_id,
                    "status": result.status,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                    "evidence_json_path": result.evidence_json_path,
                    "note_url": result.note_url,
                    "note_id": result.note_id,
                }
            )
    except Exception as exc:
        jobs.append(
            {
                "job_id": None,
                "status": STATUS_FAILED,
                "error_code": XHS_PUBLISH_BATCH_FAILED,
                "error_message": str(exc),
                "evidence_json_path": None,
                "note_url": None,
                "note_id": None,
            }
        )
    success_count = len([job for job in jobs if job["status"] == STATUS_SUCCESS])
    failed_count = len(request.jobs) - success_count
    status = STATUS_SUCCESS
    if failed_count and success_count:
        status = XHS_PUBLISH_BATCH_PARTIAL_FAILED
    elif failed_count:
        status = STATUS_FAILED
    return XhsBatchPublishResult(
        batch_id=request.batch_id,
        status=status,
        total_jobs=len(request.jobs),
        success_count=success_count,
        failed_count=failed_count,
        jobs=jobs,
        created_at=created_at,
        finished_at=_utc_now_iso(),
    )


@router.get("/publish/jobs/{job_id}/status")
def get_publish_job_status(job_id: str) -> dict:
    """Return local publish job state from evidence and trigger files."""
    evidence_path = publish_evidence_service.evidence_root / job_id / "publish_evidence.json"
    trigger_path = local_rpa_queue_service.queue_root / "pending" / f"_trigger_publish_{job_id}.trigger"
    evidence_dir = publish_evidence_service.evidence_root / job_id
    if evidence_path.exists():
        try:
            evidence = publish_evidence_service.read_publish_evidence(evidence_path)
            return {
                "job_id": job_id,
                "status": evidence.status or STATUS_SUCCESS,
                "evidence_json_path": str(evidence_path),
                "error_code": evidence.error_code,
                "error_message": evidence.error_message,
            }
        except WorkerError as exc:
            return {
                "job_id": job_id,
                "status": STATUS_FAILED,
                "error_code": exc.error_code,
                "error_message": exc.error_message,
                "evidence_json_path": str(evidence_path),
            }
    if trigger_path.exists():
        return {"job_id": job_id, "status": "pending"}
    if evidence_dir.exists():
        return {"job_id": job_id, "status": "processing"}
    return {
        "job_id": job_id,
        "status": "not_found",
        "error_code": XHS_PUBLISH_JOB_NOT_FOUND,
        "error_message": f"XHS publish job not found: {job_id}",
    }


@router.get("/publish/jobs/{job_id}/evidence", response_model=None)
def get_publish_job_evidence(job_id: str):
    """Return local publish evidence for a job."""
    evidence_path = publish_evidence_service.evidence_root / job_id / "publish_evidence.json"
    try:
        evidence = publish_evidence_service.read_publish_evidence(evidence_path)
        return _model_to_dict(evidence)
    except WorkerError as exc:
        return _error_response(exc, status_code=404 if exc.error_code == XHS_PUBLISH_EVIDENCE_NOT_FOUND else 400)


@router.get("/publish/{job_id}", response_model=JobStatus)
def get_publish_job(job_id: str) -> JobStatus:
    """Return an in-memory publish job status for legacy callers."""
    job_status = job_registry.get_job(job_id)
    if job_status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job_status


def _utc_now_iso() -> str:
    """Return a UTC timestamp."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _model_to_dict(value):
    """Convert Pydantic models to dictionaries across versions."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _error_response(exc: WorkerError, status_code: int) -> JSONResponse:
    """Return a structured WorkerError response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": STATUS_FAILED,
            "error_code": exc.error_code,
            "error_message": exc.error_message,
        },
    )
