import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.schemas import ExternalReadinessResult, KuaJingVSDiscoveryHardenResult, KuaJingVSDiscoveryResult, SearchJob, WorkerResult
from app.services.audit_log_service import AuditLogService
from app.services.external_readiness_service import ExternalReadinessService
from app.services.feishu_write_service import FeishuWriteService
from app.services.kuaijingvs_discovery_service import KuaJingVSDiscoveryService
from app.services.kuaijingvs_discovery_hardening_service import KuaJingVSDiscoveryHardeningService
from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.local_e2e_replay_service import LocalE2EReplayService
from app.services.local_persistence_replay_service import LocalPersistenceReplayService
from app.services.minio_storage_service import MinioStorageService
from app.services.n8n_dispatch_smoke_service import N8nDispatchSmokeService
from app.services.n8n_handshake_service import N8nHandshakeService
from app.services.postgres_persistence_service import PostgresPersistenceService
from app.services.yingdao_desktop_smoke_service import YingdaoDesktopSmokeService
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService
from app.services.yingdao_actual_form_fill_smoke_service import YingdaoActualFormFillSmokeService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_EXTERNAL_LIVE_CHECK_DISABLED,
    XHS_EXTERNAL_READINESS_ERROR,
    XHS_YINGDAO_DESKTOP_SMOKE_ERROR,
    XHS_YINGDAO_FORM_SIMULATOR_ERROR,
    XHS_YINGDAO_HTML_SANDBOX_ERROR,
    XHS_YINGDAO_SELECTOR_MAPPING_ERROR,
    XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR,
    XHS_ACCOUNT_BINDING_ERROR,
    XHS_KJVS_DISCOVERY_HARDENING_ERROR,
    MINIO_UPLOAD_FAILED,
    XHS_POSTGRES_PERSISTENCE_ERROR,
    error_to_dict,
    make_error_result,
    WorkerError,
)


router = APIRouter(tags=["xhs-workflows"])
readiness_service = ExternalReadinessService()
audit_log_service = AuditLogService()
kuaijingvs_discovery_service = KuaJingVSDiscoveryService()
kuaijingvs_hardening_service = KuaJingVSDiscoveryHardeningService()
yingdao_handoff_service = YingdaoLocalHandoffService()
yingdao_desktop_smoke_service = YingdaoDesktopSmokeService()
yingdao_form_simulator_service = YingdaoFormFillSimulatorService()
yingdao_html_sandbox_service = YingdaoLocalHtmlSandboxService()
yingdao_selector_mapping_service = YingdaoSelectorMappingService()
yingdao_actual_form_fill_service = YingdaoActualFormFillSmokeService()
xhs_account_binding_service = XhsAccountBindingService()
local_contract_replay_service = LocalContractReplayService(account_binding_service=xhs_account_binding_service)
local_persistence_replay_service = LocalPersistenceReplayService(
    contract_replay_service=local_contract_replay_service,
    account_binding_service=xhs_account_binding_service,
)
local_e2e_replay_service = LocalE2EReplayService(
    readiness_service=readiness_service,
    account_binding_service=xhs_account_binding_service,
    contract_replay_service=local_contract_replay_service,
    persistence_replay_service=local_persistence_replay_service,
)
postgres_persistence_service = PostgresPersistenceService()
minio_storage_service = MinioStorageService()
feishu_write_service = FeishuWriteService()
n8n_dispatch_smoke_service = N8nDispatchSmokeService(
    feishu_write_service=feishu_write_service,
    minio_storage_service=minio_storage_service,
    postgres_persistence_service=postgres_persistence_service,
)
n8n_handshake_service = N8nHandshakeService()


class YingdaoPublishHandoffRequest(BaseModel):
    """Request for preparing a local Yingdao publish handoff."""

    job_id: str
    account_id: str
    provider_type: str = "yingdao_local_file_trigger"
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class YingdaoSmokeSearchPrepareRequest(BaseModel):
    """Request for preparing a Yingdao desktop search smoke test."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class YingdaoSmokePublishPrepareRequest(BaseModel):
    """Request for preparing a Yingdao desktop publish smoke test."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)


class YingdaoSmokeMockWriteRequest(BaseModel):
    """Request for local-only mock smoke writes."""

    status: str = "success"


class YingdaoFormSimulatorSearchPrepareRequest(BaseModel):
    """Request for preparing a browserless search form simulator package."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class YingdaoFormSimulatorPublishPrepareRequest(BaseModel):
    """Request for preparing a browserless publish form simulator package."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class YingdaoFormSimulatorMockWriteRequest(BaseModel):
    """Request for local-only browserless simulator mock writes."""

    status: str = "success"


class YingdaoHtmlSandboxSearchPrepareRequest(BaseModel):
    """Request for preparing a local search HTML sandbox."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class YingdaoHtmlSandboxPublishPrepareRequest(BaseModel):
    """Request for preparing a local publish HTML sandbox."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class YingdaoHtmlSandboxMockWriteRequest(BaseModel):
    """Request for local-only HTML sandbox mock writes."""

    status: str = "success"


class YingdaoSelectorMappingSearchPrepareRequest(BaseModel):
    """Request for preparing local selector mapping for search sandbox."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class YingdaoSelectorMappingPublishPrepareRequest(BaseModel):
    """Request for preparing local selector mapping for publish sandbox."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class YingdaoSelectorMappingMockConfirmRequest(BaseModel):
    """Request for local-only selector confirmation mock writes."""

    status: str = "success"


class YingdaoActualFormFillSearchPrepareRequest(BaseModel):
    """Request for preparing actual local search form-fill smoke."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class YingdaoActualFormFillPublishPrepareRequest(BaseModel):
    """Request for preparing actual local publish form-fill smoke."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class YingdaoActualFormFillMockWriteRequest(BaseModel):
    """Request for local-only actual form-fill mock writes."""

    status: str = "success"


class XhsAccountBindingSearchPrepareRequest(BaseModel):
    """Request for preparing search account binding."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class XhsAccountBindingPublishPrepareRequest(BaseModel):
    """Request for preparing publish account binding."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class XhsAccountBindingMockConfirmRequest(BaseModel):
    """Request for local-only account binding mock confirmation."""

    status: str = "success"


class KuaJingVSDiscoveryHardenApiRequest(BaseModel):
    """Request for local KuaJingVS discovery evidence hardening."""

    source_evidence_path: str | None = None


class XhsContractReplaySearchRequest(BaseModel):
    """Request for local n8n search contract replay."""

    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class XhsContractReplayPublishRequest(BaseModel):
    """Request for local n8n publish contract replay."""

    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class XhsOpenClawStatusReplayRequest(BaseModel):
    """Request for local OpenClaw job-status contract replay."""

    job_id: str
    job_type: str
    account_id: str


class XhsPersistenceReplayApiRequest(BaseModel):
    """Request for local Feishu/PostgreSQL/MinIO mock persistence replay."""

    job_id: str
    account_id: str
    source_replay_result_path: str | None = None
    source_replay_summary_path: str | None = None
    strict_mode: bool = True
    dry_run: bool = True


class XhsE2EReplaySearchApiRequest(BaseModel):
    """Request for local full E2E search replay."""

    run_id: str
    job_id: str
    account_id: str
    keyword: str
    limit: int = 20


class XhsE2EReplayPublishApiRequest(BaseModel):
    """Request for local full E2E publish replay."""

    run_id: str
    job_id: str
    account_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class XhsE2EReplayAllApiRequest(BaseModel):
    """Request for local full E2E search plus publish replay."""

    run_id: str
    account_id: str
    search_job_id: str | None = None
    publish_job_id: str | None = None
    keyword: str
    limit: int = 20
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    publish_mode: str = "manual_review"


class XhsPostgresPersistenceApiRequest(BaseModel):
    """Request for controlled PostgreSQL persistence from replay payload."""

    job_id: str
    account_id: str
    persistence_payload_path: str | None = None
    dry_run: bool = True
    require_safe_payload: bool = True


class XhsMinioStorageApiRequest(BaseModel):
    """Request for controlled MinIO storage planning or upload."""

    job_id: str
    account_id: str
    provider_type: str | None = None
    evidence_dir: str | None = None
    sources: list[dict] | None = None
    dry_run: bool = True
    overwrite: bool = False
    include_optional_missing: bool = True
    object_prefix: str | None = None


class XhsFeishuWriteApiRequest(BaseModel):
    """Request for controlled Feishu write planning or explicit write."""

    job_id: str
    account_id: str | None = None
    operation: str = "upsert_plan_only"
    feishu_record_id: str | None = None
    source_result_path: str | None = None
    source_summary_path: str | None = None
    records: list[dict] | None = None
    dry_run: bool = True
    table_id: str | None = None
    app_token: str | None = None
    field_mapping: dict[str, str] | None = None
    include_raw_payload: bool = True


class XhsFeishuReadbackApiRequest(BaseModel):
    """Request for controlled single-record Feishu readback smoke."""

    job_id: str
    account_id: str | None = None
    operation: str = "readback"
    feishu_record_id: str | None = None
    records: list[dict] | None = None
    dry_run: bool = True
    table_id: str | None = None
    app_token: str | None = None
    field_mapping: dict[str, str] | None = None


class XhsN8nDispatchApiRequest(BaseModel):
    """Request for local n8n-style dry-run dispatch smoke."""

    job_id: str
    account_id: str
    trigger_source: str = "n8n_smoke"
    dry_run: bool = True
    steps: list[str] | None = None
    payload: dict | None = None
    base_url: str = "http://127.0.0.1:8000"


class XhsN8nHandshakeApiRequest(BaseModel):
    """Request for controlled n8n webhook handshake smoke."""

    handshake_id: str
    job_id: str
    account_id: str | None = None
    dry_run: bool = True
    webhook_url: str | None = None
    marker: str = "XHS_N8N_HANDSHAKE_SMOKE"
    payload: dict | None = None


@router.get("/api/workflows/xhs/external-readiness", response_model=None)
def get_external_readiness() -> ExternalReadinessResult | JSONResponse:
    """Return safe external readiness status without live external calls."""
    try:
        result = readiness_service.check_all()
        audit_log_service.append_event(
            event_type="external_readiness_check",
            status=result.status,
            message="external readiness checked",
            actor="local_api",
            metadata={
                "safe_mode": result.safe_mode,
                "readiness_mode": result.metadata.get("readiness_mode"),
                "summary": _model_to_dict(result.summary),
            },
        )
        return result
    except Exception as exc:
        try:
            audit_log_service.append_event(
                event_type="external_readiness_check",
                status="failed",
                error_code=XHS_EXTERNAL_READINESS_ERROR,
                message="external readiness check failed",
                actor="local_api",
                metadata={"safe_mode": True, "readiness_mode": "dry_run"},
            )
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content=make_error_result(
                XHS_EXTERNAL_READINESS_ERROR,
                f"external readiness check failed: {exc}",
            ),
        )


@router.get("/api/workflows/xhs/kuaijingvs/discovery", response_model=None)
def get_kuaijingvs_discovery() -> KuaJingVSDiscoveryResult | JSONResponse:
    """Run explicit KuaJingVS live-readonly discovery."""
    try:
        if not kuaijingvs_discovery_service.adapter.is_live_readonly_enabled():
            exc = WorkerError(
                error_code=XHS_EXTERNAL_LIVE_CHECK_DISABLED,
                error_message=(
                    "KuaJingVS live readonly discovery is disabled. "
                    "Set XHS_ALLOW_LIVE_READONLY_CHECKS=true and restart browser-worker."
                ),
                retryable=False,
            )
            audit_log_service.append_event(
                event_type="kuaijingvs_live_readonly_discovery",
                status="blocked",
                error_code=exc.error_code,
                message="KuaJingVS live readonly discovery blocked",
                actor="local_api",
                metadata={
                    "safe_mode": True,
                    "live_readonly_enabled": False,
                },
            )
            return JSONResponse(status_code=400, content=error_to_dict(exc, status="blocked"))

        result = kuaijingvs_discovery_service.discover()
        audit_log_service.append_event(
            event_type="kuaijingvs_live_readonly_discovery",
            status=result.status,
            error_code=result.error_code,
            message="KuaJingVS live readonly discovery completed",
            actor="local_api",
            metadata={
                "safe_mode": result.safe_mode,
                "live_readonly_enabled": result.live_readonly_enabled,
                "shop_count": result.shop_count,
                "profile_map_valid": result.profile_map_valid,
                "matched_account_count": result.matched_account_count,
                "unmatched_account_count": result.unmatched_account_count,
                "evidence_json_path": result.evidence_json_path,
            },
        )
        return result
    except WorkerError as exc:
        try:
            audit_log_service.append_event(
                event_type="kuaijingvs_live_readonly_discovery",
                status="failed",
                error_code=exc.error_code,
                message="KuaJingVS live readonly discovery failed",
                actor="local_api",
                metadata={"safe_mode": True},
            )
        except Exception:
            pass
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/kuaijingvs/discovery/harden", response_model=None)
def harden_kuaijingvs_discovery(request: KuaJingVSDiscoveryHardenApiRequest) -> KuaJingVSDiscoveryHardenResult | JSONResponse:
    """Harden local KuaJingVS discovery evidence without live network or open-shop."""
    try:
        result = kuaijingvs_hardening_service.harden_discovery_evidence(request.source_evidence_path)
        audit_log_service.append_event(
            event_type="kuaijingvs_discovery_hardened",
            status=result.status,
            error_code=result.error_code,
            message="KuaJingVS discovery evidence hardened",
            actor="local_api",
            metadata={
                "source_evidence_path": request.source_evidence_path,
                "hardened_evidence_path": result.hardened_evidence_path,
                "summary_path": result.summary_path,
                "shop_count": result.shop_count,
                "sensitive_key_removed_count": (result.summary or {}).get("sensitive_key_removed_count"),
                "sensitive_value_scan_passed": result.sensitive_value_scan_passed,
                "evidence_hash": result.evidence_hash,
            },
        )
        return result
    except Exception as exc:
        try:
            audit_log_service.append_event(
                event_type="kuaijingvs_discovery_hardened",
                status="failed",
                error_code=XHS_KJVS_DISCOVERY_HARDENING_ERROR,
                message="KuaJingVS discovery hardening failed",
                actor="local_api",
                metadata={"source_evidence_path": request.source_evidence_path},
            )
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content=make_error_result(
                XHS_KJVS_DISCOVERY_HARDENING_ERROR,
                f"KuaJingVS discovery hardening failed: {exc}",
            ),
        )


@router.post("/api/workflows/xhs/yingdao/local-handoff/search", response_model=None)
def prepare_yingdao_search_handoff(job: SearchJob) -> dict | JSONResponse:
    """Prepare a local active search job for Yingdao file handoff."""
    try:
        result = yingdao_handoff_service.prepare_search_handoff(job)
        audit_log_service.append_event(
            event_type="yingdao_local_search_handoff_prepared",
            job_id=job.job_id,
            status="accepted",
            message="Yingdao local search handoff prepared",
            actor="local_api",
            metadata={
                "job_id": job.job_id,
                "account_id": job.account_id,
                "active_job_path": result.active_job_path,
                "expected_evidence_path": result.expected_evidence_path,
                "safe_mode": True,
            },
        )
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/local-handoff/publish", response_model=None)
def prepare_yingdao_publish_handoff(job: YingdaoPublishHandoffRequest) -> dict | JSONResponse:
    """Prepare a local active publish job for Yingdao file handoff."""
    try:
        result = yingdao_handoff_service.prepare_publish_handoff(job)
        audit_log_service.append_event(
            event_type="yingdao_local_publish_handoff_prepared",
            job_id=job.job_id,
            status="accepted",
            message="Yingdao local publish handoff prepared",
            actor="local_api",
            metadata={
                "job_id": job.job_id,
                "account_id": job.account_id,
                "active_job_path": result.active_job_path,
                "expected_evidence_path": result.expected_evidence_path,
                "safe_mode": True,
                "image_count": len(job.image_paths),
                "tag_count": len(job.tags),
            },
        )
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.get("/api/workflows/xhs/yingdao/local-handoff/search/{job_id}", response_model=None)
def get_yingdao_search_handoff_result(job_id: str) -> WorkerResult | JSONResponse:
    """Read local search evidence and return a WorkerResult-shaped response."""
    read_result = yingdao_handoff_service.read_search_evidence(job_id)
    _append_evidence_read_audit(job_id, "search", read_result)
    if read_result.worker_result:
        return WorkerResult(**read_result.worker_result)
    return WorkerResult(
        job_id=job_id,
        status=read_result.status,
        message=read_result.message,
        error_code=read_result.error_code,
        error_message=read_result.error_message,
        evidence_json_path=read_result.evidence_json_path,
    )


@router.get("/api/workflows/xhs/yingdao/local-handoff/publish/{job_id}", response_model=None)
def get_yingdao_publish_handoff_result(job_id: str) -> WorkerResult | JSONResponse:
    """Read local publish evidence and return a WorkerResult-shaped response."""
    read_result = yingdao_handoff_service.read_publish_evidence(job_id)
    _append_evidence_read_audit(job_id, "publish", read_result)
    if read_result.worker_result:
        return WorkerResult(**read_result.worker_result)
    return WorkerResult(
        job_id=job_id,
        status=read_result.status,
        message=read_result.message,
        error_code=read_result.error_code,
        error_message=read_result.error_message,
        evidence_json_path=read_result.evidence_json_path,
    )


@router.get("/api/workflows/xhs/yingdao/local-handoff/active")
def get_yingdao_active_handoff_jobs() -> dict:
    """Return shallow active job status for local Yingdao handoff files."""
    return yingdao_handoff_service.get_active_job_status()


@router.post("/api/workflows/xhs/yingdao/desktop-smoke/search/prepare", response_model=None)
def prepare_yingdao_desktop_search_smoke(job: YingdaoSmokeSearchPrepareRequest) -> dict | JSONResponse:
    """Prepare active search job and smoke paths for manual Yingdao desktop testing."""
    try:
        result = yingdao_desktop_smoke_service.prepare_search_smoke(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_desktop_smoke_prepare_audit(
            "yingdao_desktop_search_smoke_prepared",
            result,
        )
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/desktop-smoke/publish/prepare", response_model=None)
def prepare_yingdao_desktop_publish_smoke(job: YingdaoSmokePublishPrepareRequest) -> dict | JSONResponse:
    """Prepare active publish job and smoke paths for manual Yingdao desktop testing."""
    try:
        result = yingdao_desktop_smoke_service.prepare_publish_smoke(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
        )
        _append_desktop_smoke_prepare_audit(
            "yingdao_desktop_publish_smoke_prepared",
            result,
        )
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.get("/api/workflows/xhs/yingdao/desktop-smoke/search/{job_id}/verify", response_model=None)
def verify_yingdao_desktop_search_smoke(job_id: str) -> dict | JSONResponse:
    """Verify manual Yingdao desktop search smoke receipt and evidence."""
    return _verify_desktop_smoke("search", job_id)


@router.get("/api/workflows/xhs/yingdao/desktop-smoke/publish/{job_id}/verify", response_model=None)
def verify_yingdao_desktop_publish_smoke(job_id: str) -> dict | JSONResponse:
    """Verify manual Yingdao desktop publish smoke receipt and evidence."""
    return _verify_desktop_smoke("publish", job_id)


@router.post("/api/workflows/xhs/yingdao/desktop-smoke/{job_type}/{job_id}/mock-write", response_model=None)
def mock_write_yingdao_desktop_smoke(job_type: str, job_id: str, request: YingdaoSmokeMockWriteRequest) -> dict | JSONResponse:
    """Local-only helper that simulates Yingdao writing receipt and evidence."""
    try:
        if str(os.getenv("YINGDAO_DESKTOP_SMOKE_ALLOW_MOCK_WRITE", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
            raise WorkerError(
                error_code=XHS_YINGDAO_DESKTOP_SMOKE_ERROR,
                error_message="Yingdao desktop smoke mock-write is disabled",
            )
        receipt_path = yingdao_desktop_smoke_service.write_mock_receipt_for_local_test(job_type, job_id)
        evidence_path = yingdao_desktop_smoke_service.write_mock_evidence_for_local_test(
            job_type,
            job_id,
            request.status,
        )
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "evidence_written",
            "receipt_path": receipt_path,
            "evidence_path": evidence_path,
            "message": "local mock receipt and evidence written; no external system was called",
        }
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/form-simulator/search/prepare", response_model=None)
def prepare_yingdao_form_simulator_search(job: YingdaoFormSimulatorSearchPrepareRequest) -> dict | JSONResponse:
    """Prepare a browserless search form-fill simulator package."""
    try:
        result = yingdao_form_simulator_service.prepare_search_simulator(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_form_simulator_prepare_audit("yingdao_form_simulator_search_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/form-simulator/publish/prepare", response_model=None)
def prepare_yingdao_form_simulator_publish(job: YingdaoFormSimulatorPublishPrepareRequest) -> dict | JSONResponse:
    """Prepare a browserless publish form-fill simulator package."""
    try:
        result = yingdao_form_simulator_service.prepare_publish_simulator(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_form_simulator_prepare_audit("yingdao_form_simulator_publish_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.get("/api/workflows/xhs/yingdao/form-simulator/search/{job_id}/verify", response_model=None)
def verify_yingdao_form_simulator_search(job_id: str) -> dict | JSONResponse:
    """Verify browserless search form-fill simulator trace/result."""
    return _verify_form_simulator("search", job_id)


@router.get("/api/workflows/xhs/yingdao/form-simulator/publish/{job_id}/verify", response_model=None)
def verify_yingdao_form_simulator_publish(job_id: str) -> dict | JSONResponse:
    """Verify browserless publish form-fill simulator trace/result."""
    return _verify_form_simulator("publish", job_id)


@router.post("/api/workflows/xhs/yingdao/form-simulator/{job_type}/{job_id}/mock-write", response_model=None)
def mock_write_yingdao_form_simulator(
    job_type: str,
    job_id: str,
    request: YingdaoFormSimulatorMockWriteRequest,
) -> dict | JSONResponse:
    """Local-only helper that simulates browserless form-fill trace/result writes."""
    try:
        if str(os.getenv("YINGDAO_FORM_SIMULATOR_ALLOW_MOCK_WRITE", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
            raise WorkerError(
                error_code=XHS_YINGDAO_FORM_SIMULATOR_ERROR,
                error_message="Yingdao form simulator mock-write is disabled",
            )
        paths = yingdao_form_simulator_service.write_mock_trace_and_result(job_type, job_id, request.status)
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "simulator_result_written",
            **paths,
            "message": "local browserless form-fill trace and result written; no external system was called",
        }
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/html-sandbox/search/prepare", response_model=None)
def prepare_yingdao_html_sandbox_search(job: YingdaoHtmlSandboxSearchPrepareRequest) -> dict | JSONResponse:
    """Prepare a local static search HTML sandbox."""
    try:
        result = yingdao_html_sandbox_service.prepare_search_sandbox(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_html_sandbox_prepare_audit("yingdao_html_sandbox_search_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/html-sandbox/publish/prepare", response_model=None)
def prepare_yingdao_html_sandbox_publish(job: YingdaoHtmlSandboxPublishPrepareRequest) -> dict | JSONResponse:
    """Prepare a local static publish HTML sandbox."""
    try:
        result = yingdao_html_sandbox_service.prepare_publish_sandbox(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_html_sandbox_prepare_audit("yingdao_html_sandbox_publish_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.get("/api/workflows/xhs/yingdao/html-sandbox/search/{job_id}/verify", response_model=None)
def verify_yingdao_html_sandbox_search(job_id: str) -> dict | JSONResponse:
    """Verify local static search HTML sandbox trace/result."""
    return _verify_html_sandbox("search", job_id)


@router.get("/api/workflows/xhs/yingdao/html-sandbox/publish/{job_id}/verify", response_model=None)
def verify_yingdao_html_sandbox_publish(job_id: str) -> dict | JSONResponse:
    """Verify local static publish HTML sandbox trace/result."""
    return _verify_html_sandbox("publish", job_id)


@router.post("/api/workflows/xhs/yingdao/html-sandbox/{job_type}/{job_id}/mock-write", response_model=None)
def mock_write_yingdao_html_sandbox(
    job_type: str,
    job_id: str,
    request: YingdaoHtmlSandboxMockWriteRequest,
) -> dict | JSONResponse:
    """Local-only helper that simulates HTML sandbox trace/result writes."""
    try:
        if str(os.getenv("YINGDAO_HTML_SANDBOX_ALLOW_MOCK_WRITE", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
            raise WorkerError(
                error_code=XHS_YINGDAO_HTML_SANDBOX_ERROR,
                error_message="Yingdao local HTML sandbox mock-write is disabled",
            )
        paths = yingdao_html_sandbox_service.write_mock_trace_and_result(job_type, job_id, request.status)
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "sandbox_result_written",
            **paths,
            "message": "local HTML sandbox trace and result written; no external system was called",
        }
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/selector-mapping/search/prepare", response_model=None)
def prepare_yingdao_selector_mapping_search(job: YingdaoSelectorMappingSearchPrepareRequest) -> dict | JSONResponse:
    """Prepare local HTML selector mapping report for search sandbox."""
    try:
        result = yingdao_selector_mapping_service.prepare_search_mapping(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_selector_mapping_prepare_audit("yingdao_selector_mapping_search_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/selector-mapping/publish/prepare", response_model=None)
def prepare_yingdao_selector_mapping_publish(job: YingdaoSelectorMappingPublishPrepareRequest) -> dict | JSONResponse:
    """Prepare local HTML selector mapping report for publish sandbox."""
    try:
        result = yingdao_selector_mapping_service.prepare_publish_mapping(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_selector_mapping_prepare_audit("yingdao_selector_mapping_publish_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.get("/api/workflows/xhs/yingdao/selector-mapping/search/{job_id}/verify", response_model=None)
def verify_yingdao_selector_mapping_search(job_id: str) -> dict | JSONResponse:
    """Verify local search selector mapping confirmation."""
    return _verify_selector_mapping("search", job_id)


@router.get("/api/workflows/xhs/yingdao/selector-mapping/publish/{job_id}/verify", response_model=None)
def verify_yingdao_selector_mapping_publish(job_id: str) -> dict | JSONResponse:
    """Verify local publish selector mapping confirmation."""
    return _verify_selector_mapping("publish", job_id)


@router.post("/api/workflows/xhs/yingdao/selector-mapping/{job_type}/{job_id}/mock-confirm", response_model=None)
def mock_confirm_yingdao_selector_mapping(
    job_type: str,
    job_id: str,
    request: YingdaoSelectorMappingMockConfirmRequest,
) -> dict | JSONResponse:
    """Local-only helper that simulates Yingdao selector confirmation."""
    try:
        if str(os.getenv("YINGDAO_SELECTOR_MAPPING_ALLOW_MOCK_CONFIRM", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
            raise WorkerError(
                error_code=XHS_YINGDAO_SELECTOR_MAPPING_ERROR,
                error_message="Yingdao selector mapping mock-confirm is disabled",
            )
        paths = yingdao_selector_mapping_service.write_mock_confirmation(job_type, job_id, request.status)
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "selector_mapping_confirmed",
            **paths,
            "message": "local selector mapping confirmation written; no external system was called",
        }
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/actual-form-fill/search/prepare", response_model=None)
def prepare_yingdao_actual_form_fill_search(job: YingdaoActualFormFillSearchPrepareRequest) -> dict | JSONResponse:
    """Prepare actual local HTML form-fill smoke for search sandbox."""
    try:
        result = yingdao_actual_form_fill_service.prepare_search_actual_fill(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_actual_form_fill_prepare_audit("yingdao_actual_form_fill_search_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/yingdao/actual-form-fill/publish/prepare", response_model=None)
def prepare_yingdao_actual_form_fill_publish(job: YingdaoActualFormFillPublishPrepareRequest) -> dict | JSONResponse:
    """Prepare actual local HTML form-fill smoke for publish sandbox."""
    try:
        result = yingdao_actual_form_fill_service.prepare_publish_actual_fill(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_actual_form_fill_prepare_audit("yingdao_actual_form_fill_publish_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.get("/api/workflows/xhs/yingdao/actual-form-fill/search/{job_id}/verify", response_model=None)
def verify_yingdao_actual_form_fill_search(job_id: str) -> dict | JSONResponse:
    """Verify actual local search form-fill trace/result."""
    return _verify_actual_form_fill("search", job_id)


@router.get("/api/workflows/xhs/yingdao/actual-form-fill/publish/{job_id}/verify", response_model=None)
def verify_yingdao_actual_form_fill_publish(job_id: str) -> dict | JSONResponse:
    """Verify actual local publish form-fill trace/result."""
    return _verify_actual_form_fill("publish", job_id)


@router.post("/api/workflows/xhs/yingdao/actual-form-fill/{job_type}/{job_id}/mock-write", response_model=None)
def mock_write_yingdao_actual_form_fill(
    job_type: str,
    job_id: str,
    request: YingdaoActualFormFillMockWriteRequest,
) -> dict | JSONResponse:
    """Local-only helper that simulates actual local form-fill trace/result writes."""
    try:
        if str(os.getenv("YINGDAO_ACTUAL_FORM_FILL_ALLOW_MOCK_WRITE", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
            raise WorkerError(
                error_code=XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR,
                error_message="Yingdao actual local form-fill mock-write is disabled",
            )
        paths = yingdao_actual_form_fill_service.write_mock_trace_and_result(job_type, job_id, request.status)
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "actual_form_fill_result_written",
            **paths,
            "message": "local actual form-fill trace and result written; no external system was called",
        }
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/account-binding/search/prepare", response_model=None)
def prepare_xhs_account_binding_search(job: XhsAccountBindingSearchPrepareRequest) -> dict | JSONResponse:
    """Prepare search account binding context without opening shops or XHS."""
    try:
        result = xhs_account_binding_service.prepare_search_account_binding(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_account_binding_prepare_audit("xhs_account_binding_search_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/account-binding/publish/prepare", response_model=None)
def prepare_xhs_account_binding_publish(job: XhsAccountBindingPublishPrepareRequest) -> dict | JSONResponse:
    """Prepare publish account binding context without opening shops or XHS."""
    try:
        result = xhs_account_binding_service.prepare_publish_account_binding(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_account_binding_prepare_audit("xhs_account_binding_publish_prepared", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/account-binding/search/strict-check", response_model=None)
def strict_check_xhs_account_binding_search(job: XhsAccountBindingSearchPrepareRequest) -> dict | JSONResponse:
    """Run strict search account binding check using hardened discovery evidence."""
    try:
        result = xhs_account_binding_service.prepare_search_strict_binding_check(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_account_binding_strict_audit(result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/account-binding/publish/strict-check", response_model=None)
def strict_check_xhs_account_binding_publish(job: XhsAccountBindingPublishPrepareRequest) -> dict | JSONResponse:
    """Run strict publish account binding check using hardened discovery evidence."""
    try:
        result = xhs_account_binding_service.prepare_publish_strict_binding_check(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_account_binding_strict_audit(result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/contract-replay/n8n/search", response_model=None)
def replay_n8n_search_contract(job: XhsContractReplaySearchRequest) -> dict | JSONResponse:
    """Replay local n8n search contract without calling real n8n."""
    try:
        result = local_contract_replay_service.prepare_n8n_search_replay(
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_contract_replay_audit("local_contract_replay_n8n_search", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/contract-replay/n8n/publish", response_model=None)
def replay_n8n_publish_contract(job: XhsContractReplayPublishRequest) -> dict | JSONResponse:
    """Replay local n8n publish contract without calling real n8n."""
    try:
        result = local_contract_replay_service.prepare_n8n_publish_replay(
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_contract_replay_audit("local_contract_replay_n8n_publish", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/contract-replay/openclaw/job-status", response_model=None)
def replay_openclaw_job_status_contract(job: XhsOpenClawStatusReplayRequest) -> dict | JSONResponse:
    """Replay local OpenClaw job-status contract without calling real OpenClaw."""
    try:
        result = local_contract_replay_service.prepare_openclaw_status_replay(
            job_id=job.job_id,
            job_type=job.job_type,
            account_id=job.account_id,
        )
        _append_contract_replay_audit("local_contract_replay_openclaw_job_status", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/contract-replay/all/search", response_model=None)
def replay_all_search_contracts(job: XhsContractReplaySearchRequest) -> dict | JSONResponse:
    """Run strict binding plus local n8n/OpenClaw search contract replays."""
    try:
        result = local_contract_replay_service.replay_all_for_job(
            job_id=job.job_id,
            job_type="xhs_search",
            account_id=job.account_id,
            payload={"keyword": job.keyword, "limit": job.limit},
        )
        _append_contract_replay_all_audit(result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/contract-replay/all/publish", response_model=None)
def replay_all_publish_contracts(job: XhsContractReplayPublishRequest) -> dict | JSONResponse:
    """Run strict binding plus local n8n/OpenClaw publish contract replays."""
    try:
        result = local_contract_replay_service.replay_all_for_job(
            job_id=job.job_id,
            job_type="xhs_publish",
            account_id=job.account_id,
            payload={
                "title": job.title,
                "body": job.body,
                "tags": job.tags,
                "image_paths": job.image_paths,
                "publish_mode": job.publish_mode,
            },
        )
        _append_contract_replay_all_audit(result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/persistence-replay/feishu/search", response_model=None)
def replay_feishu_search_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate local Feishu search mock persistence payload without real writes."""
    return _replay_persistence_target("feishu", "search", job)


@router.post("/api/workflows/xhs/persistence-replay/feishu/publish", response_model=None)
def replay_feishu_publish_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate local Feishu publish mock persistence payload without real writes."""
    return _replay_persistence_target("feishu", "publish", job)


@router.post("/api/workflows/xhs/persistence-replay/postgres/search", response_model=None)
def replay_postgres_search_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate local PostgreSQL search mock persistence payload without real writes."""
    return _replay_persistence_target("postgres", "search", job)


@router.post("/api/workflows/xhs/persistence-replay/postgres/publish", response_model=None)
def replay_postgres_publish_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate local PostgreSQL publish mock persistence payload without real writes."""
    return _replay_persistence_target("postgres", "publish", job)


@router.post("/api/workflows/xhs/persistence-replay/minio/search", response_model=None)
def replay_minio_search_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate local MinIO search mock object manifest without real uploads."""
    return _replay_persistence_target("minio", "search", job)


@router.post("/api/workflows/xhs/persistence-replay/minio/publish", response_model=None)
def replay_minio_publish_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate local MinIO publish mock object manifest without real uploads."""
    return _replay_persistence_target("minio", "publish", job)


@router.post("/api/workflows/xhs/persistence-replay/all/search", response_model=None)
def replay_all_search_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate all local search mock persistence replay packages."""
    return _replay_persistence_all("search", job)


@router.post("/api/workflows/xhs/persistence-replay/all/publish", response_model=None)
def replay_all_publish_persistence(job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Generate all local publish mock persistence replay packages."""
    return _replay_persistence_all("publish", job)


@router.post("/api/workflows/xhs/e2e-replay/search", response_model=None)
def replay_search_e2e(job: XhsE2EReplaySearchApiRequest) -> dict | JSONResponse:
    """Run local full E2E search replay without real external calls."""
    try:
        result = local_e2e_replay_service.replay_search(
            run_id=job.run_id,
            job_id=job.job_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
        )
        _append_e2e_replay_audit("local_e2e_replay_search", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/e2e-replay/publish", response_model=None)
def replay_publish_e2e(job: XhsE2EReplayPublishApiRequest) -> dict | JSONResponse:
    """Run local full E2E publish replay without real external calls."""
    try:
        result = local_e2e_replay_service.replay_publish(
            run_id=job.run_id,
            job_id=job.job_id,
            account_id=job.account_id,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
        )
        _append_e2e_replay_audit("local_e2e_replay_publish", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/e2e-replay/all", response_model=None)
def replay_all_e2e(job: XhsE2EReplayAllApiRequest) -> dict | JSONResponse:
    """Run local full E2E search and publish replay without real external calls."""
    try:
        result = local_e2e_replay_service.replay_all(
            run_id=job.run_id,
            account_id=job.account_id,
            keyword=job.keyword,
            limit=job.limit,
            title=job.title,
            body=job.body,
            tags=job.tags,
            image_paths=job.image_paths,
            publish_mode=job.publish_mode,
            search_job_id=job.search_job_id,
            publish_job_id=job.publish_job_id,
        )
        _append_e2e_replay_audit("local_e2e_replay_all", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/postgres-persistence/search", response_model=None)
def persist_search_replay_to_postgres(job: XhsPostgresPersistenceApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly persist search replay payload to PostgreSQL."""
    try:
        from app.schemas import XhsPostgresPersistenceRequest

        result = postgres_persistence_service.persist_search_replay(
            XhsPostgresPersistenceRequest(
                job_id=job.job_id,
                job_type="search",
                account_id=job.account_id,
                persistence_payload_path=job.persistence_payload_path,
                dry_run=job.dry_run,
                require_safe_payload=job.require_safe_payload,
            )
        )
        _append_postgres_persistence_audit("postgres_persistence_search", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/postgres-persistence/publish", response_model=None)
def persist_publish_replay_to_postgres(job: XhsPostgresPersistenceApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly persist publish replay payload to PostgreSQL."""
    try:
        from app.schemas import XhsPostgresPersistenceRequest

        result = postgres_persistence_service.persist_publish_replay(
            XhsPostgresPersistenceRequest(
                job_id=job.job_id,
                job_type="publish",
                account_id=job.account_id,
                persistence_payload_path=job.persistence_payload_path,
                dry_run=job.dry_run,
                require_safe_payload=job.require_safe_payload,
            )
        )
        _append_postgres_persistence_audit("postgres_persistence_publish", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/minio-storage/search", response_model=None)
def plan_or_upload_search_to_minio(job: XhsMinioStorageApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly upload search artifacts to MinIO."""
    try:
        from app.schemas import XhsMinioStorageRequest, XhsMinioUploadSource

        result = minio_storage_service.upload_search_artifacts(
            XhsMinioStorageRequest(
                job_id=job.job_id,
                job_type="search",
                account_id=job.account_id,
                provider_type=job.provider_type,
                evidence_dir=job.evidence_dir,
                sources=[XhsMinioUploadSource(**item) for item in job.sources] if job.sources else None,
                dry_run=job.dry_run,
                overwrite=job.overwrite,
                include_optional_missing=job.include_optional_missing,
                object_prefix=job.object_prefix,
            )
        )
        _append_minio_storage_audit("minio_storage_search", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/minio-storage/publish", response_model=None)
def plan_or_upload_publish_to_minio(job: XhsMinioStorageApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly upload publish artifacts to MinIO."""
    try:
        from app.schemas import XhsMinioStorageRequest, XhsMinioUploadSource

        result = minio_storage_service.upload_publish_artifacts(
            XhsMinioStorageRequest(
                job_id=job.job_id,
                job_type="publish",
                account_id=job.account_id,
                provider_type=job.provider_type,
                evidence_dir=job.evidence_dir,
                sources=[XhsMinioUploadSource(**item) for item in job.sources] if job.sources else None,
                dry_run=job.dry_run,
                overwrite=job.overwrite,
                include_optional_missing=job.include_optional_missing,
                object_prefix=job.object_prefix,
            )
        )
        _append_minio_storage_audit("minio_storage_publish", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/feishu-write/search", response_model=None)
def plan_or_write_search_to_feishu(job: XhsFeishuWriteApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly write search payload to Feishu."""
    try:
        from app.schemas import XhsFeishuWriteRequest

        result = feishu_write_service.plan_or_write_search(
            XhsFeishuWriteRequest(
                job_id=job.job_id,
                job_type="search",
                account_id=job.account_id,
                operation=job.operation,
                feishu_record_id=job.feishu_record_id,
                source_result_path=job.source_result_path,
                source_summary_path=job.source_summary_path,
                records=job.records,
                dry_run=job.dry_run,
                table_id=job.table_id,
                app_token=job.app_token,
                field_mapping=job.field_mapping,
                include_raw_payload=job.include_raw_payload,
            )
        )
        _append_feishu_write_audit("feishu_write_search", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/feishu-write/publish", response_model=None)
def plan_or_write_publish_to_feishu(job: XhsFeishuWriteApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly write publish payload to Feishu."""
    try:
        from app.schemas import XhsFeishuWriteRequest

        result = feishu_write_service.plan_or_write_publish(
            XhsFeishuWriteRequest(
                job_id=job.job_id,
                job_type="publish",
                account_id=job.account_id,
                operation=job.operation,
                feishu_record_id=job.feishu_record_id,
                source_result_path=job.source_result_path,
                source_summary_path=job.source_summary_path,
                records=job.records,
                dry_run=job.dry_run,
                table_id=job.table_id,
                app_token=job.app_token,
                field_mapping=job.field_mapping,
                include_raw_payload=job.include_raw_payload,
            )
        )
        _append_feishu_write_audit("feishu_write_publish", result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/feishu-readback/search", response_model=None)
def readback_search_from_feishu(job: XhsFeishuReadbackApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly read back one Feishu search smoke record."""
    try:
        from app.schemas import XhsFeishuReadbackRequest

        result = feishu_write_service.readback_search(
            XhsFeishuReadbackRequest(
                job_id=job.job_id,
                job_type="search",
                account_id=job.account_id,
                operation=job.operation,
                feishu_record_id=job.feishu_record_id,
                records=job.records,
                dry_run=job.dry_run,
                table_id=job.table_id,
                app_token=job.app_token,
                field_mapping=job.field_mapping,
            )
        )
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/feishu-readback/publish", response_model=None)
def readback_publish_from_feishu(job: XhsFeishuReadbackApiRequest) -> dict | JSONResponse:
    """Dry-run or explicitly read back one Feishu publish smoke record."""
    try:
        from app.schemas import XhsFeishuReadbackRequest

        result = feishu_write_service.readback_publish(
            XhsFeishuReadbackRequest(
                job_id=job.job_id,
                job_type="publish",
                account_id=job.account_id,
                operation=job.operation,
                feishu_record_id=job.feishu_record_id,
                records=job.records,
                dry_run=job.dry_run,
                table_id=job.table_id,
                app_token=job.app_token,
                field_mapping=job.field_mapping,
            )
        )
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


@router.post("/api/workflows/xhs/n8n-dispatch/search", response_model=None)
def dispatch_n8n_search_dry_run(job: XhsN8nDispatchApiRequest) -> dict | JSONResponse:
    """Run local n8n-style search dry-run dispatch smoke without real n8n."""
    return _dispatch_n8n_smoke("search", job)


@router.post("/api/workflows/xhs/n8n-dispatch/publish", response_model=None)
def dispatch_n8n_publish_dry_run(job: XhsN8nDispatchApiRequest) -> dict | JSONResponse:
    """Run local n8n-style publish dry-run dispatch smoke without real n8n."""
    return _dispatch_n8n_smoke("publish", job)


@router.post("/api/workflows/xhs/n8n-dispatch/full-dry-run", response_model=None)
def dispatch_n8n_full_dry_run(job: XhsN8nDispatchApiRequest) -> dict | JSONResponse:
    """Run local n8n-style full dry-run dispatch smoke without real n8n."""
    return _dispatch_n8n_smoke("full", job)


@router.post("/api/workflows/xhs/n8n-handshake/ping", response_model=None)
def handshake_n8n_ping(job: XhsN8nHandshakeApiRequest) -> dict | JSONResponse:
    """Run controlled n8n ping handshake smoke."""
    return _run_n8n_handshake("ping", job)


@router.post("/api/workflows/xhs/n8n-handshake/search", response_model=None)
def handshake_n8n_search(job: XhsN8nHandshakeApiRequest) -> dict | JSONResponse:
    """Run controlled n8n search handshake smoke without triggering search."""
    return _run_n8n_handshake("search", job)


@router.post("/api/workflows/xhs/n8n-handshake/publish", response_model=None)
def handshake_n8n_publish(job: XhsN8nHandshakeApiRequest) -> dict | JSONResponse:
    """Run controlled n8n publish handshake smoke without triggering publish."""
    return _run_n8n_handshake("publish", job)


@router.post("/api/workflows/xhs/n8n-handshake/full", response_model=None)
def handshake_n8n_full(job: XhsN8nHandshakeApiRequest) -> dict | JSONResponse:
    """Run controlled n8n full-chain handshake smoke without triggering workflows."""
    return _run_n8n_handshake("full", job)


@router.get("/api/workflows/xhs/account-binding/search/{job_id}/verify", response_model=None)
def verify_xhs_account_binding_search(job_id: str) -> dict | JSONResponse:
    """Verify search account binding confirmation."""
    return _verify_account_binding("search", job_id)


@router.get("/api/workflows/xhs/account-binding/publish/{job_id}/verify", response_model=None)
def verify_xhs_account_binding_publish(job_id: str) -> dict | JSONResponse:
    """Verify publish account binding confirmation."""
    return _verify_account_binding("publish", job_id)


@router.post("/api/workflows/xhs/account-binding/{job_type}/{job_id}/mock-confirm", response_model=None)
def mock_confirm_xhs_account_binding(
    job_type: str,
    job_id: str,
    request: XhsAccountBindingMockConfirmRequest,
) -> dict | JSONResponse:
    """Local-only helper that simulates account binding confirmation."""
    try:
        if str(os.getenv("XHS_ACCOUNT_BINDING_ALLOW_MOCK_CONFIRM", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
            raise WorkerError(
                error_code=XHS_ACCOUNT_BINDING_ERROR,
                error_message="XHS account binding mock-confirm is disabled",
            )
        paths = xhs_account_binding_service.write_mock_confirmation(job_type, job_id, request.status)
        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "account_binding_confirmed",
            **paths,
            "message": "local account binding confirmation written; no external system was called",
        }
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _model_to_dict(value):
    """Convert Pydantic models to dictionaries across versions."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _append_evidence_read_audit(job_id: str, job_kind: str, read_result) -> None:
    """Append audit event for local evidence reads without blocking API responses."""
    try:
        audit_log_service.append_event(
            event_type="yingdao_local_evidence_read",
            job_id=job_id,
            status=read_result.status,
            error_code=read_result.error_code,
            message=f"Yingdao local {job_kind} evidence read",
            actor="local_api",
            metadata={
                "job_id": job_id,
                "job_kind": job_kind,
                "evidence_json_path": read_result.evidence_json_path,
            },
        )
    except Exception:
        pass


def _append_desktop_smoke_prepare_audit(event_type: str, result) -> None:
    """Append audit for desktop smoke preparation."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status="waiting_desktop_rpa",
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "active_job_path": result.active_job_path,
                "expected_receipt_path": result.expected_receipt_path,
                "expected_evidence_path": result.expected_evidence_path,
            },
        )
    except Exception:
        pass


def _verify_desktop_smoke(job_type: str, job_id: str) -> dict | JSONResponse:
    """Verify a desktop smoke job and append audit."""
    try:
        result = yingdao_desktop_smoke_service.verify_smoke(job_type, job_id)
        try:
            audit_log_service.append_event(
                event_type="yingdao_desktop_smoke_verified",
                job_id=job_id,
                status=result.status,
                error_code=result.error_code,
                message=result.message,
                actor="local_api",
                metadata={
                    "job_id": job_id,
                    "job_type": result.job_type,
                    "receipt_valid": result.summary.receipt_valid,
                    "evidence_valid": result.summary.evidence_valid,
                    "opened_browser": result.summary.opened_browser,
                    "opened_xhs": result.summary.opened_xhs,
                    "real_action_executed": result.summary.real_action_executed,
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _append_form_simulator_prepare_audit(event_type: str, result) -> None:
    """Append audit for form simulator preparation."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status="waiting_simulator_result",
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "simulator_dir": result.simulator_dir,
                "form_spec_path": result.form_spec_path,
                "expected_actions_path": result.expected_actions_path,
            },
        )
    except Exception:
        pass


def _verify_form_simulator(job_type: str, job_id: str) -> dict | JSONResponse:
    """Verify form simulator trace/result and append audit."""
    try:
        result = yingdao_form_simulator_service.verify_simulator(job_type, job_id)
        try:
            audit_log_service.append_event(
                event_type="yingdao_form_simulator_verified",
                job_id=job_id,
                status=result.status,
                error_code=result.error_code,
                message=result.message,
                actor="local_api",
                metadata={
                    "job_id": job_id,
                    "job_type": result.job_type,
                    "simulator_dir": result.simulator_dir,
                    "trace_valid": result.summary.trace_valid,
                    "result_valid": result.summary.result_valid,
                    "opened_browser": result.summary.opened_browser,
                    "opened_xhs": result.summary.opened_xhs,
                    "called_external_api": result.summary.called_external_api,
                    "clicked_real_publish": result.summary.clicked_real_publish,
                    "real_action_executed": result.summary.real_action_executed,
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _append_html_sandbox_prepare_audit(event_type: str, result) -> None:
    """Append audit for HTML sandbox preparation."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status="waiting_sandbox_result",
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "sandbox_dir": result.sandbox_dir,
                "html_path": result.html_path,
                "expected_dom_path": result.expected_dom_path,
            },
        )
    except Exception:
        pass


def _verify_html_sandbox(job_type: str, job_id: str) -> dict | JSONResponse:
    """Verify HTML sandbox trace/result and append audit."""
    try:
        result = yingdao_html_sandbox_service.verify_sandbox(job_type, job_id)
        try:
            audit_log_service.append_event(
                event_type="yingdao_html_sandbox_verified",
                job_id=job_id,
                status=result.status,
                error_code=result.error_code,
                message=result.message,
                actor="local_api",
                metadata={
                    "job_id": job_id,
                    "job_type": result.job_type,
                    "sandbox_dir": result.sandbox_dir,
                    "trace_valid": result.summary.trace_valid,
                    "result_valid": result.summary.result_valid,
                    "opened_external_url": result.summary.opened_external_url,
                    "opened_xhs": result.summary.opened_xhs,
                    "called_external_api": result.summary.called_external_api,
                    "clicked_real_publish": result.summary.clicked_real_publish,
                    "real_action_executed": result.summary.real_action_executed,
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _append_selector_mapping_prepare_audit(event_type: str, result) -> None:
    """Append audit for selector mapping preparation."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status="waiting_selector_confirmation",
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "mapping_dir": result.mapping_dir,
                "selector_mapping_path": result.selector_mapping_path,
                "action_sequence_path": result.action_sequence_path,
                "mapping_report_path": result.mapping_report_path,
            },
        )
    except Exception:
        pass


def _verify_selector_mapping(job_type: str, job_id: str) -> dict | JSONResponse:
    """Verify selector mapping confirmation and append audit."""
    try:
        result = yingdao_selector_mapping_service.verify_mapping(job_type, job_id)
        try:
            audit_log_service.append_event(
                event_type="yingdao_selector_mapping_verified",
                job_id=job_id,
                status=result.status,
                error_code=result.error_code,
                message=result.message,
                actor="local_api",
                metadata={
                    "job_id": job_id,
                    "job_type": result.job_type,
                    "mapping_dir": result.mapping_dir,
                    "confirmation_valid": result.summary.confirmation_valid,
                    "opened_external_url": result.summary.opened_external_url,
                    "opened_xhs": result.summary.opened_xhs,
                    "called_external_api": result.summary.called_external_api,
                    "clicked_real_publish": result.summary.clicked_real_publish,
                    "real_action_executed": result.summary.real_action_executed,
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _append_actual_form_fill_prepare_audit(event_type: str, result) -> None:
    """Append audit for actual local form-fill preparation."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status="waiting_actual_form_fill_result",
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "actual_form_fill_dir": result.actual_form_fill_dir,
                "html_uri": result.html_uri,
                "runbook_path": result.actual_form_fill_runbook_path,
                "expected_trace_path": result.expected_trace_path,
                "expected_result_path": result.expected_result_path,
            },
        )
    except Exception:
        pass


def _verify_actual_form_fill(job_type: str, job_id: str) -> dict | JSONResponse:
    """Verify actual local form-fill trace/result and append audit."""
    try:
        result = yingdao_actual_form_fill_service.verify_actual_form_fill(job_type, job_id)
        try:
            audit_log_service.append_event(
                event_type="yingdao_actual_form_fill_verified",
                job_id=job_id,
                status=result.status,
                error_code=result.error_code,
                message=result.message,
                actor="local_api",
                metadata={
                    "job_id": job_id,
                    "job_type": result.job_type,
                    "actual_form_fill_dir": result.actual_form_fill_dir,
                    "trace_valid": result.summary.trace_valid,
                    "result_valid": result.summary.result_valid,
                    "opened_local_html": result.summary.opened_local_html,
                    "opened_external_url": result.summary.opened_external_url,
                    "opened_xhs": result.summary.opened_xhs,
                    "called_external_api": result.summary.called_external_api,
                    "clicked_real_publish": result.summary.clicked_real_publish,
                    "real_action_executed": result.summary.real_action_executed,
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _append_account_binding_prepare_audit(event_type: str, result) -> None:
    """Append audit for account binding preparation."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "account_id": getattr(result, "account_id", None),
                "binding_status": result.binding_status,
                "account_binding_context_path": result.account_binding_context_path,
            },
        )
    except Exception:
        pass


def _append_account_binding_strict_audit(result) -> None:
    """Append audit for strict account binding checks."""
    try:
        audit_log_service.append_event(
            event_type="xhs_account_binding_strict_checked",
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="XHS account binding strict mode checked",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "account_id": result.account_id,
                "shop_id": (result.matched_profile.shop_id if result.matched_profile else None),
                "binding_status": result.binding_status,
                "strict_binding_result_path": result.strict_binding_result_path,
                "profile_map_exists": result.checks.get("profile_map_exists"),
                "hardened_discovery_exists": result.checks.get("hardened_discovery_exists"),
                "shop_id_matched": result.checks.get("shop_id_matched"),
                "shop_name_matched": result.checks.get("shop_name_matched"),
                "provider_type_allowed": result.checks.get("provider_type_allowed"),
            },
        )
    except Exception:
        pass


def _append_contract_replay_audit(event_type: str, result) -> None:
    """Append audit for local n8n/OpenClaw contract replay."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message=result.message,
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "target": result.target,
                "local_route": result.local_route,
                "replay_payload_path": result.replay_payload_path,
                "replay_result_path": result.replay_result_path,
                "strict_binding_status": result.strict_binding_status,
                "sensitive_scan_passed": result.sensitive_scan_passed,
                "external_calls_made": result.external_calls_made,
            },
        )
    except Exception:
        pass


def _append_contract_replay_all_audit(result) -> None:
    """Append audit for replay-all local contract checks."""
    try:
        audit_log_service.append_event(
            event_type="local_contract_replay_all",
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="local contract replay all completed",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "strict_binding_status": result.strict_binding_status,
                "n8n_status": (result.n8n_replay or {}).get("status") if result.n8n_replay else None,
                "openclaw_status": (result.openclaw_replay or {}).get("status") if result.openclaw_replay else None,
            },
        )
    except Exception:
        pass


def _replay_persistence_target(target: str, job_type: str, job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Replay one local persistence target and append audit."""
    try:
        if target == "feishu":
            result = local_persistence_replay_service.replay_feishu_mock(
                job_id=job.job_id,
                job_type=job_type,
                account_id=job.account_id,
                source_replay_result_path=job.source_replay_result_path,
                source_replay_summary_path=job.source_replay_summary_path,
            )
            event_type = f"local_persistence_replay_feishu_{job_type}"
        elif target == "postgres":
            result = local_persistence_replay_service.replay_postgres_mock(
                job_id=job.job_id,
                job_type=job_type,
                account_id=job.account_id,
                source_replay_result_path=job.source_replay_result_path,
                source_replay_summary_path=job.source_replay_summary_path,
            )
            event_type = f"local_persistence_replay_postgres_{job_type}"
        else:
            result = local_persistence_replay_service.replay_minio_mock(
                job_id=job.job_id,
                job_type=job_type,
                account_id=job.account_id,
                source_replay_result_path=job.source_replay_result_path,
                source_replay_summary_path=job.source_replay_summary_path,
            )
            event_type = f"local_persistence_replay_minio_{job_type}"
        _append_persistence_replay_audit(event_type, result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _replay_persistence_all(job_type: str, job: XhsPersistenceReplayApiRequest) -> dict | JSONResponse:
    """Replay all local persistence targets and append audit."""
    try:
        result = local_persistence_replay_service.replay_all_for_job(
            job_id=job.job_id,
            job_type=job_type,
            account_id=job.account_id,
        )
        _append_persistence_replay_all_audit(result)
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _append_persistence_replay_audit(event_type: str, result) -> None:
    """Append audit for local Feishu/PostgreSQL/MinIO mock persistence replay."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="local mock persistence replay completed",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "target": result.target,
                "payload_path": result.payload_path,
                "result_path": result.result_path,
                "summary_path": result.summary_path,
                "strict_binding_status": result.strict_binding_status,
                "hardened_discovery_status": result.hardened_discovery_status,
                "source_replay_status": result.source_replay_status,
                "sensitive_payload_detected": result.sensitive_payload_detected,
                "external_write_forbidden": result.external_write_forbidden,
            },
        )
    except Exception:
        pass


def _append_persistence_replay_all_audit(result) -> None:
    """Append audit for all local persistence replay targets."""
    try:
        audit_log_service.append_event(
            event_type="local_persistence_replay_all",
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="local persistence replay all completed",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "feishu_status": (result.feishu or {}).get("status") if result.feishu else None,
                "postgres_status": (result.postgres or {}).get("status") if result.postgres else None,
                "minio_status": (result.minio or {}).get("status") if result.minio else None,
                "result_path": result.result_path,
                "summary_path": result.summary_path,
            },
        )
    except Exception:
        pass


def _append_e2e_replay_audit(event_type: str, result) -> None:
    """Append audit for local full E2E replay without sensitive payloads."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.run_id,
            status=result.status,
            error_code=result.error_code,
            message="local full E2E replay completed",
            actor="local_api",
            metadata={
                "run_id": result.run_id,
                "job_type": result.job_type,
                "e2e_input_path": result.e2e_input_path,
                "e2e_result_path": result.e2e_result_path,
                "e2e_summary_path": result.e2e_summary_path,
                "artifacts_manifest_path": result.artifacts_manifest_path,
                "step_statuses": [{"step_name": step.step_name, "status": step.status} for step in result.steps],
                "sensitive_payload_detected": result.sensitive_payload_detected,
                "external_call_forbidden": result.external_call_forbidden,
            },
        )
    except Exception:
        pass


def _append_postgres_persistence_audit(event_type: str, result) -> None:
    """Append audit for controlled PostgreSQL persistence without sensitive payloads."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="controlled PostgreSQL persistence completed",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "account_id": result.account_id,
                "dry_run": result.dry_run,
                "rows_planned": result.rows_planned,
                "rows_written": result.rows_written,
                "target_tables": result.target_tables,
                "payload_path": result.payload_path,
                "plan_path": result.plan_path,
                "result_path": result.result_path,
                "summary_path": result.summary_path,
                "postgres_write_enabled": result.postgres_write_enabled,
                "sensitive_payload_detected": result.sensitive_payload_detected,
            },
        )
    except Exception:
        pass


def _append_minio_storage_audit(event_type: str, result) -> None:
    """Append audit for controlled MinIO storage without credentials."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="controlled MinIO storage completed",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "account_id": result.account_id,
                "dry_run": result.dry_run,
                "bucket": result.bucket,
                "upload_enabled": result.upload_enabled,
                "real_upload_allowed": result.real_upload_allowed,
                "uploaded_count": result.uploaded_count,
                "skipped_count": result.skipped_count,
                "plan_path": result.plan_path,
                "result_path": result.result_path,
                "summary_path": result.summary_path,
                "sensitive_file_detected": result.sensitive_file_detected,
            },
        )
    except Exception:
        pass


def _append_feishu_write_audit(event_type: str, result) -> None:
    """Append audit for controlled Feishu writes without credentials."""
    try:
        audit_log_service.append_event(
            event_type=event_type,
            job_id=result.job_id,
            status=result.status,
            error_code=result.error_code,
            message="controlled Feishu write planning completed",
            actor="local_api",
            metadata={
                "job_id": result.job_id,
                "job_type": result.job_type,
                "account_id": result.account_id,
                "operation": result.operation,
                "dry_run": result.dry_run,
                "target_table_kind": result.target_table_kind,
                "record_count": result.record_count,
                "written_count": result.written_count,
                "write_enabled": result.write_enabled,
                "real_write_allowed": result.real_write_allowed,
                "plan_path": result.plan_path,
                "payload_path": result.payload_path,
                "result_path": result.result_path,
                "summary_path": result.summary_path,
                "sensitive_payload_detected": result.sensitive_payload_detected,
            },
        )
    except Exception:
        pass


def _dispatch_n8n_smoke(job_type: str, job: XhsN8nDispatchApiRequest) -> dict | JSONResponse:
    """Run local n8n dispatch smoke and append audit without external calls."""
    try:
        from app.schemas import XhsN8nDispatchRequest

        result = n8n_dispatch_smoke_service.execute_local_dry_run_dispatch(
            XhsN8nDispatchRequest(
                job_id=job.job_id,
                job_type=job_type,
                account_id=job.account_id,
                trigger_source=job.trigger_source,
                dry_run=job.dry_run,
                steps=job.steps,
                payload=job.payload,
                base_url=job.base_url,
            )
        )
        try:
            audit_log_service.append_event(
                event_type=f"n8n_dispatch_{job_type}",
                job_id=result.job_id,
                status=result.status,
                error_code=result.error_code,
                message="local n8n dry-run dispatch smoke completed",
                actor="local_api",
                metadata={
                    "job_id": result.job_id,
                    "job_type": result.job_type,
                    "dry_run": result.dry_run,
                    "request_path": result.request_path,
                    "result_path": result.result_path,
                    "summary_path": result.summary_path,
                    "external_calls_made": result.external_calls_made,
                    "step_count": len(result.steps),
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _run_n8n_handshake(job_type: str, job: XhsN8nHandshakeApiRequest) -> dict | JSONResponse:
    """Run controlled n8n handshake and append audit without leaking webhook secrets."""
    try:
        from app.schemas import XhsN8nHandshakeRequest

        response = n8n_handshake_service.execute_handshake(
            XhsN8nHandshakeRequest(
                handshake_id=job.handshake_id,
                job_id=job.job_id,
                job_type=job_type,
                account_id=job.account_id,
                dry_run=job.dry_run,
                webhook_url=job.webhook_url,
                marker=job.marker,
                payload=job.payload,
            )
        )
        try:
            paths = n8n_handshake_service.get_output_paths(job.handshake_id, job_type)
            audit_log_service.append_event(
                event_type=f"n8n_handshake_{job_type}",
                job_id=job.job_id,
                status="success" if response.response_valid else "failed",
                error_code=response.error_code,
                message="controlled n8n handshake smoke completed",
                actor="local_api",
                metadata={
                    "handshake_id": response.handshake_id,
                    "job_id": response.job_id,
                    "job_type": response.job_type,
                    "dry_run": response.dry_run,
                    "http_status": response.http_status,
                    "response_valid": response.response_valid,
                    "marker_confirmed": response.marker_confirmed,
                    "external_call_made": response.external_call_made,
                    "request_path": paths["request_path"],
                    "response_path": paths["response_path"],
                    "summary_path": paths["summary_path"],
                },
            )
        except Exception:
            pass
        payload = _model_to_dict(response)
        paths = n8n_handshake_service.get_output_paths(job.handshake_id, job_type)
        payload.update(
            {
                "status": "success" if response.error_code is None else "failed",
                "request_path": paths["request_path"],
                "response_path": paths["response_path"],
                "summary_path": paths["summary_path"],
            }
        )
        return payload
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))


def _verify_account_binding(job_type: str, job_id: str) -> dict | JSONResponse:
    """Verify account binding confirmation and append audit."""
    try:
        result = xhs_account_binding_service.verify_account_binding(job_type, job_id)
        try:
            audit_log_service.append_event(
                event_type="xhs_account_binding_verified",
                job_id=job_id,
                status=result.status,
                error_code=result.error_code,
                message=result.message,
                actor="local_api",
                metadata={
                    "job_id": job_id,
                    "job_type": result.job_type,
                    "account_id": result.summary.account_id,
                    "shop_id": result.summary.shop_id,
                    "binding_status": result.summary.binding_status,
                    "confirmation_valid": result.summary.confirmation_valid,
                    "opened_shop": result.summary.opened_shop,
                    "opened_xhs": result.summary.opened_xhs,
                    "called_yingdao_openapi": result.summary.called_yingdao_openapi,
                    "called_kuaijingvs_open_shop": result.summary.called_kuaijingvs_open_shop,
                    "real_action_executed": result.summary.real_action_executed,
                },
            )
        except Exception:
            pass
        return _model_to_dict(result)
    except WorkerError as exc:
        return JSONResponse(status_code=400, content=error_to_dict(exc))
