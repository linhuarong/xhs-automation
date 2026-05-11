from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.publish import create_publish_batch
from app.api.search import create_keyword_batch
from app.schemas import (
    XhsBatchKeywordRequest,
    XhsBatchPublishRequest,
    XhsPublishAsset,
    XhsPublishJob,
    XhsSearchToPublishWorkflowRequest,
    XhsWorkflowResult,
)
from app.services.local_rpa_queue import LocalRpaQueueService
from app.services.xhs_job_registry import xhs_job_registry
from app.services.xhs_workflow_service import XhsWorkflowService
from app.utils.errors import (
    XHS_WEBHOOK_UNSUPPORTED_EVENT,
    error_to_dict,
    make_error_result,
    WorkerError,
)


router = APIRouter(tags=["xhs-webhooks"])
workflow_service = XhsWorkflowService()
local_rpa_queue_service = LocalRpaQueueService()


class N8nSearchWebhookRequest(BaseModel):
    """n8n XHS keyword search webhook payload."""

    workflow_id: str
    batch_id: str
    account_id: str
    provider_type: str
    keywords: list[str]
    limit: int = 20
    callback_url: str | None = None


class N8nPublishWebhookJob(BaseModel):
    """n8n XHS publish webhook job payload."""

    job_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    assets: list[XhsPublishAsset] = Field(default_factory=list)


class N8nPublishWebhookRequest(BaseModel):
    """n8n XHS publish webhook payload."""

    workflow_id: str
    batch_id: str
    account_id: str
    provider_type: str
    jobs: list[N8nPublishWebhookJob]
    callback_url: str | None = None


class OpenClawJobStatusRequest(BaseModel):
    """OpenClaw job status request."""

    job_id: str
    job_type: str


@router.post("/api/webhooks/n8n/xhs/search")
def n8n_xhs_search_webhook(request: N8nSearchWebhookRequest):
    """Convert an n8n search webhook into an internal batch request."""
    batch_request = XhsBatchKeywordRequest(
        batch_id=request.batch_id,
        account_id=request.account_id,
        provider_type=request.provider_type,
        keywords=request.keywords,
        limit=request.limit,
        mode="sync",
    )
    result = create_keyword_batch(batch_request)
    xhs_job_registry.register_batch(
        request.batch_id,
        "search",
        [job.get("job_id") for job in result.jobs if job.get("job_id")],
    )
    xhs_job_registry.update_batch_summary(request.batch_id, _model_to_dict(result))
    return result


@router.post("/api/webhooks/n8n/xhs/publish")
def n8n_xhs_publish_webhook(request: N8nPublishWebhookRequest):
    """Convert an n8n publish webhook into an internal publish batch request."""
    jobs = [
        XhsPublishJob(
            job_id=job.job_id,
            account_id=request.account_id,
            provider_type=request.provider_type,
            title=job.title,
            body=job.body,
            tags=job.tags,
            assets=job.assets,
        )
        for job in request.jobs
    ]
    batch_request = XhsBatchPublishRequest(
        batch_id=request.batch_id,
        account_id=request.account_id,
        provider_type=request.provider_type,
        jobs=jobs,
        mode="sync",
    )
    result = create_publish_batch(batch_request)
    xhs_job_registry.register_batch(
        request.batch_id,
        "publish",
        [job.get("job_id") for job in result.jobs if job.get("job_id")],
    )
    xhs_job_registry.update_batch_summary(request.batch_id, _model_to_dict(result))
    return result


@router.post("/api/webhooks/openclaw/xhs/job-status")
def openclaw_xhs_job_status(request: OpenClawJobStatusRequest):
    """Return registry status for OpenClaw."""
    if request.job_type not in {"search", "publish"}:
        return JSONResponse(
            status_code=400,
            content=make_error_result(
                XHS_WEBHOOK_UNSUPPORTED_EVENT,
                f"unsupported job_type: {request.job_type}",
            ),
        )
    job = xhs_job_registry.get_job(request.job_id)
    return {
        "job_id": request.job_id,
        "job_type": request.job_type,
        "status": job.get("status"),
        "result": job.get("result"),
        "evidence_json_path": (job.get("result") or {}).get("evidence_json_path")
        if isinstance(job.get("result"), dict)
        else None,
        "error_code": job.get("error_code"),
        "error_message": job.get("error_message"),
    }


@router.get("/api/workflows/xhs/health")
def xhs_workflow_health() -> dict:
    """Return local workflow contract health."""
    return {
        "status": "ok",
        "supported_provider_types": [
            "selenium_chrome",
            "yingdao_rpa",
            "yingdao_local_file_trigger",
            "kuaijingvs_yingdao_rpa",
            "kuaijingvs_local_file_trigger",
            "kuaijingvs_local_file_trigger_publish",
            "manual",
        ],
        "local_queue_root": str(local_rpa_queue_service.queue_root),
        "local_evidence_root": str(local_rpa_queue_service.evidence_root),
        "external_integrations_mode": "mock",
    }


@router.post("/api/xhs/workflows/search-to-publish/mock", response_model=None)
def run_search_to_publish_mock_workflow(
    request: XhsSearchToPublishWorkflowRequest,
):
    """Run a fully local mock search-to-publish workflow."""
    try:
        return workflow_service.run_search_to_publish_mock_workflow(request)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _model_to_dict(value):
    """Convert Pydantic models to dictionaries across versions."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)
