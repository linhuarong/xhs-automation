import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.xhs_search_core import search_xhs_keyword
from app.providers import get_provider
from app.schemas import (
    STATUS_ACCEPTED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_WAITING_HUMAN_VERIFICATION,
    SearchJob,
    WorkerResult,
    XhsBatchKeywordRequest,
    XhsBatchKeywordResult,
)
from app.services.local_rpa_queue import LocalRpaQueueService
from app.services.xhs_evidence_service import XhsEvidenceService
from app.services import job_registry
from app.utils.errors import (
    XHS_BATCH_FAILED,
    XHS_BATCH_PARTIAL_FAILED,
    XHS_EVIDENCE_INVALID,
    XHS_EVIDENCE_NOT_FOUND,
    XHS_JOB_NOT_FOUND,
    WorkerError,
)


router = APIRouter(prefix="/api/xhs", tags=["xhs-search"])
evidence_service = XhsEvidenceService()
local_rpa_queue_service = LocalRpaQueueService()


class NormalizeEvidenceRequest(BaseModel):
    """Normalize evidence JSON request."""

    evidence_json_path: str
    write_back: bool = True


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


@router.post("/search/normalize", response_model=None)
def normalize_search_evidence(request: NormalizeEvidenceRequest):
    """Normalize an existing XHS search evidence JSON file."""
    try:
        evidence = evidence_service.read_evidence(request.evidence_json_path)
        if request.write_back:
            evidence = evidence_service.write_normalized_evidence(evidence, request.evidence_json_path)
        return {
            "status": STATUS_SUCCESS,
            "normalized_record_count": evidence.normalized_record_count or 0,
            "normalized_records": [_model_to_dict(record) for record in evidence.normalized_records],
        }
    except WorkerError as exc:
        return _error_response(exc, status_code=404 if exc.error_code == XHS_EVIDENCE_NOT_FOUND else 400)


@router.post("/keywords/batch", response_model=XhsBatchKeywordResult)
def create_keyword_batch(request: XhsBatchKeywordRequest) -> XhsBatchKeywordResult:
    """Run a sync keyword batch through the configured provider."""
    created_at = _utc_now_iso()
    jobs: list[dict] = []
    if request.mode != "sync":
        return XhsBatchKeywordResult(
            batch_id=request.batch_id,
            status=STATUS_FAILED,
            total_keywords=len(request.keywords),
            success_count=0,
            failed_count=len(request.keywords),
            jobs=[],
            created_at=created_at,
            finished_at=_utc_now_iso(),
        )

    try:
        provider = get_provider(request.provider_type)
        for index, keyword in enumerate(request.keywords, start=1):
            job_id = f"{request.batch_id}-{_safe_keyword(keyword)}-{index}"
            job = SearchJob(
                job_id=job_id,
                account_id=request.account_id,
                provider_type=request.provider_type,
                keyword=keyword,
                limit=request.limit,
            )
            try:
                search = getattr(provider, "search", None)
                result = search(job) if callable(search) else search_xhs_keyword(job, provider)
            except WorkerError as exc:
                result = WorkerResult(
                    job_id=job_id,
                    status=STATUS_FAILED,
                    error_code=exc.error_code,
                    error_message=exc.error_message,
                )
            except Exception as exc:
                result = WorkerResult(
                    job_id=job_id,
                    status=STATUS_FAILED,
                    error_code=XHS_BATCH_FAILED,
                    error_message=str(exc),
                )
            jobs.append(
                {
                    "job_id": result.job_id,
                    "keyword": keyword,
                    "status": result.status,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                    "evidence_json_path": result.evidence_json_path,
                }
            )
    except Exception as exc:
        jobs.append(
            {
                "job_id": None,
                "keyword": None,
                "status": STATUS_FAILED,
                "error_code": XHS_BATCH_FAILED,
                "error_message": str(exc),
                "evidence_json_path": None,
            }
        )

    success_count = len([job for job in jobs if job["status"] == STATUS_SUCCESS])
    failed_count = len(request.keywords) - success_count
    status = STATUS_SUCCESS
    if failed_count and success_count:
        status = XHS_BATCH_PARTIAL_FAILED
    elif failed_count:
        status = STATUS_FAILED
    return XhsBatchKeywordResult(
        batch_id=request.batch_id,
        status=status,
        total_keywords=len(request.keywords),
        success_count=success_count,
        failed_count=failed_count,
        jobs=jobs,
        created_at=created_at,
        finished_at=_utc_now_iso(),
    )


@router.get("/jobs/{job_id}/evidence", response_model=None)
def get_job_evidence(job_id: str):
    """Return local evidence with normalized records for a job."""
    evidence_path = evidence_service.evidence_root / job_id / "search_evidence.json"
    try:
        evidence = evidence_service.read_evidence(evidence_path)
        return _model_to_dict(evidence)
    except WorkerError as exc:
        return _error_response(exc, status_code=404 if exc.error_code == XHS_EVIDENCE_NOT_FOUND else 400)


@router.get("/jobs/{job_id}/status")
def get_xhs_job_status(job_id: str) -> dict:
    """Return local job state from evidence and trigger files."""
    evidence_path = evidence_service.evidence_root / job_id / "search_evidence.json"
    trigger_path = local_rpa_queue_service.queue_root / "pending" / f"_trigger_{job_id}.trigger"
    evidence_dir = evidence_service.evidence_root / job_id
    if evidence_path.exists():
        try:
            evidence = evidence_service.read_evidence(evidence_path)
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
        "error_code": XHS_JOB_NOT_FOUND,
        "error_message": f"XHS job not found: {job_id}",
    }


def _utc_now_iso() -> str:
    """Return a UTC timestamp."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_keyword(keyword: str) -> str:
    """Build a path-safe keyword segment."""
    safe = re.sub(r"[^\w-]+", "-", keyword.strip(), flags=re.UNICODE).strip("-")
    return safe or "keyword"


def _model_to_dict(value):
    """Convert Pydantic models to dictionaries across Pydantic versions."""
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
            "error_code": exc.error_code or XHS_EVIDENCE_INVALID,
            "error_message": exc.error_message,
        },
    )
