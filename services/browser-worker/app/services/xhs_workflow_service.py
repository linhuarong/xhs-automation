from datetime import UTC, datetime
from pathlib import Path

from app.integrations.feishu_adapter import MockFeishuAdapter
from app.integrations.postgres_repository import InMemoryXhsRepository
from app.schemas import STATUS_FAILED, STATUS_SUCCESS
from app.schemas.xhs_workflow import XhsSearchToPublishWorkflowRequest, XhsWorkflowResult
from app.services.audit_log_service import AuditLogService
from app.services.xhs_evidence_service import XhsEvidenceService
from app.services.xhs_job_registry import InMemoryXhsJobRegistry, xhs_job_registry
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService
from app.services.xhs_storage_service import XhsStorageService
from app.utils.errors import XHS_E2E_MOCK_FAILED, XHS_WORKFLOW_PARTIAL_FAILED, WorkerError


class XhsWorkflowService:
    """Mock XHS search-to-publish workflow orchestration."""

    def __init__(
        self,
        registry: InMemoryXhsJobRegistry | None = None,
        audit_log: AuditLogService | None = None,
        storage_service: XhsStorageService | None = None,
        search_evidence_service: XhsEvidenceService | None = None,
        publish_evidence_service: XhsPublishEvidenceService | None = None,
        feishu_adapter: MockFeishuAdapter | None = None,
        repository: InMemoryXhsRepository | None = None,
    ) -> None:
        """Create a mock workflow service."""
        self.registry = registry or xhs_job_registry
        self.audit_log = audit_log or AuditLogService()
        self.storage_service = storage_service or XhsStorageService()
        self.search_evidence_service = search_evidence_service or XhsEvidenceService(
            self.storage_service.evidence_root
        )
        self.publish_evidence_service = publish_evidence_service or XhsPublishEvidenceService(
            self.storage_service.evidence_root
        )
        self.feishu_adapter = feishu_adapter or MockFeishuAdapter()
        self.repository = repository or InMemoryXhsRepository()

    def run_search_to_publish_mock_workflow(
        self,
        request: XhsSearchToPublishWorkflowRequest,
    ) -> XhsWorkflowResult:
        """Run a fully local mock search-to-publish workflow."""
        created_at = self._utc_now_iso()
        search_batch_id = f"{request.workflow_id}-search"
        publish_batch_id = f"{request.workflow_id}-publish"
        archived_files: list[dict] = []
        try:
            self.audit_log.append_event(
                "batch_created",
                batch_id=search_batch_id,
                status="pending",
                message="mock search batch created",
                payload={"workflow_id": request.workflow_id},
            )
            search_summary = self._run_mock_search_batch(request, search_batch_id, archived_files)
            records = [
                record
                for job in search_summary["jobs"]
                for record in job.get("normalized_records", [])
            ]
            if not records:
                publish_summary = {
                    "batch_id": publish_batch_id,
                    "status": STATUS_FAILED,
                    "total_jobs": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "jobs": [],
                    "error_code": XHS_E2E_MOCK_FAILED,
                    "error_message": "mock workflow produced no normalized records.",
                }
            else:
                publish_summary = self._run_mock_publish_batch(
                    request,
                    publish_batch_id,
                    records[: request.max_publish_jobs],
                    archived_files,
                )

            status = self._workflow_status(search_summary, publish_summary)
            error_code = XHS_WORKFLOW_PARTIAL_FAILED if status == XHS_WORKFLOW_PARTIAL_FAILED else None
            if publish_summary.get("error_code") and not publish_summary.get("jobs"):
                error_code = publish_summary["error_code"]
            result = XhsWorkflowResult(
                workflow_id=request.workflow_id,
                status=status,
                search_batch_id=search_batch_id,
                publish_batch_id=publish_batch_id,
                search_summary=search_summary,
                publish_summary=publish_summary,
                archived_files=archived_files,
                error_code=error_code,
                error_message=publish_summary.get("error_message"),
                created_at=created_at,
                finished_at=self._utc_now_iso(),
            )
            result_dict = self._model_to_dict(result)
            workflow_archive = self.storage_service.archive_workflow_manifest(request.workflow_id, result_dict)
            result.archived_files.append(workflow_archive)
            self.registry.update_batch_summary(request.workflow_id, self._model_to_dict(result))
            self.feishu_adapter.upsert_workflow_summary(self._model_to_dict(result))
            self.repository.save_workflow_result(self._model_to_dict(result))
            self.audit_log.append_event(
                "batch_completed" if result.status == STATUS_SUCCESS else "batch_partial_failed",
                batch_id=request.workflow_id,
                status=result.status,
                error_code=result.error_code,
                message="mock workflow finished",
                payload=self._model_to_dict(result),
            )
            return result
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(
                error_code=XHS_E2E_MOCK_FAILED,
                error_message=f"mock XHS workflow failed: {exc}",
                retryable=False,
            ) from exc

    def _run_mock_search_batch(
        self,
        request: XhsSearchToPublishWorkflowRequest,
        batch_id: str,
        archived_files: list[dict],
    ) -> dict:
        """Run local mock search jobs."""
        jobs = []
        self.registry.register_batch(batch_id, "search", [])
        for index, keyword in enumerate(request.keywords, start=1):
            job_id = f"{batch_id}-{index}"
            self.registry.register_job(job_id, "search", {"batch_id": batch_id, "keyword": keyword})
            self.audit_log.append_event("search_job_created", job_id=job_id, batch_id=batch_id, status="pending")
            if "fail-search" in keyword:
                job = {
                    "job_id": job_id,
                    "keyword": keyword,
                    "status": STATUS_FAILED,
                    "error_code": "MOCK_SEARCH_FAILED",
                    "error_message": "mock search failed",
                    "normalized_records": [],
                }
                self.registry.update_job_status(job_id, STATUS_FAILED, job, "MOCK_SEARCH_FAILED", "mock search failed")
                self.audit_log.append_event("search_job_failed", job_id=job_id, batch_id=batch_id, status=STATUS_FAILED)
                jobs.append(job)
                continue
            records = [] if "empty" in keyword else [
                {
                    "job_id": job_id,
                    "keyword": keyword,
                    "account_id": request.account_id,
                    "provider_type": request.search_provider_type,
                    "rank": 1,
                    "title": f"{keyword} mock result",
                    "engagement_score": 100,
                }
            ]
            paths = self.search_evidence_service.ensure_evidence_paths(job_id)
            self.search_evidence_service.write_normalized_evidence(
                {
                    "job_id": job_id,
                    "status": STATUS_SUCCESS,
                    "keyword": keyword,
                    "account_id": request.account_id,
                    "provider_type": request.search_provider_type,
                    "evidence_json_path": str(paths["expected_evidence_json_path"]),
                    "items": [],
                    "normalized_records": records,
                },
                paths["expected_evidence_json_path"],
            )
            archive = self.storage_service.archive_evidence(job_id)
            archived_files.append(archive)
            job = {
                "job_id": job_id,
                "keyword": keyword,
                "status": STATUS_SUCCESS,
                "evidence_json_path": str(paths["expected_evidence_json_path"]),
                "normalized_records": records,
            }
            self.registry.update_job_status(job_id, STATUS_SUCCESS, job)
            self.repository.save_job_result(job)
            self.repository.save_normalized_records(records)
            self.feishu_adapter.upsert_keyword_result(job)
            self.audit_log.append_event("search_job_completed", job_id=job_id, batch_id=batch_id, status=STATUS_SUCCESS)
            jobs.append(job)
        summary = self._batch_summary(batch_id, jobs, "total_keywords")
        self.registry.update_batch_summary(batch_id, summary)
        self.feishu_adapter.upsert_batch_summary(summary)
        return summary

    def _run_mock_publish_batch(
        self,
        request: XhsSearchToPublishWorkflowRequest,
        batch_id: str,
        records: list[dict],
        archived_files: list[dict],
    ) -> dict:
        """Run local mock publish jobs."""
        jobs = []
        self.registry.register_batch(batch_id, "publish", [])
        for index, record in enumerate(records, start=1):
            job_id = f"{batch_id}-{index}"
            keyword = str(record.get("keyword") or "")
            self.registry.register_job(job_id, "publish", {"batch_id": batch_id, "record": record})
            self.audit_log.append_event("publish_job_created", job_id=job_id, batch_id=batch_id, status="pending")
            failed = "fail-publish" in keyword
            status = STATUS_FAILED if failed else STATUS_SUCCESS
            paths = self.publish_evidence_service.ensure_publish_paths(job_id)
            self.publish_evidence_service.write_publish_evidence(
                {
                    "job_id": job_id,
                    "status": status,
                    "account_id": request.account_id,
                    "provider_type": request.publish_provider_type,
                    "title": f"{keyword} mock publish",
                    "evidence_json_path": str(paths["expected_evidence_json_path"]),
                    "result_screenshot_path": str(paths["result_screenshot_path"]),
                    "error_code": "MOCK_PUBLISH_FAILED" if failed else None,
                    "error_message": "mock publish failed" if failed else None,
                },
                paths["expected_evidence_json_path"],
            )
            archive = self.storage_service.archive_publish_evidence(job_id)
            archived_files.append(archive)
            job = {
                "job_id": job_id,
                "status": status,
                "evidence_json_path": str(paths["expected_evidence_json_path"]),
                "error_code": "MOCK_PUBLISH_FAILED" if failed else None,
                "error_message": "mock publish failed" if failed else None,
            }
            self.registry.update_job_status(job_id, status, job, job["error_code"], job["error_message"])
            self.repository.save_publish_result(job)
            self.feishu_adapter.upsert_publish_result(job)
            self.audit_log.append_event(
                "publish_job_failed" if failed else "publish_job_completed",
                job_id=job_id,
                batch_id=batch_id,
                status=status,
                error_code=job["error_code"],
            )
            jobs.append(job)
        summary = self._batch_summary(batch_id, jobs, "total_jobs")
        self.registry.update_batch_summary(batch_id, summary)
        self.feishu_adapter.upsert_publish_batch_summary(summary)
        return summary

    def _batch_summary(self, batch_id: str, jobs: list[dict], total_key: str) -> dict:
        """Build a batch summary."""
        success_count = len([job for job in jobs if job.get("status") == STATUS_SUCCESS])
        failed_count = len(jobs) - success_count
        status = STATUS_SUCCESS
        if failed_count and success_count:
            status = XHS_WORKFLOW_PARTIAL_FAILED
        elif failed_count:
            status = STATUS_FAILED
        return {
            "batch_id": batch_id,
            "status": status,
            total_key: len(jobs),
            "success_count": success_count,
            "failed_count": failed_count,
            "jobs": jobs,
        }

    def _workflow_status(self, search_summary: dict, publish_summary: dict) -> str:
        """Derive workflow status from search and publish summaries."""
        statuses = {search_summary.get("status"), publish_summary.get("status")}
        if XHS_WORKFLOW_PARTIAL_FAILED in statuses:
            return XHS_WORKFLOW_PARTIAL_FAILED
        if STATUS_FAILED in statuses:
            return STATUS_FAILED
        return STATUS_SUCCESS

    def _utc_now_iso(self) -> str:
        """Return a UTC timestamp."""
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _model_to_dict(self, value) -> dict:
        """Convert Pydantic models to dictionaries across versions."""
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)
