import json

from app.integrations.feishu_adapter import MockFeishuAdapter
from app.integrations.postgres_repository import InMemoryXhsRepository
from app.schemas import XhsSearchToPublishWorkflowRequest
from app.services.audit_log_service import AuditLogService
from app.services.xhs_evidence_service import XhsEvidenceService
from app.services.xhs_job_registry import InMemoryXhsJobRegistry
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService
from app.services.xhs_storage_service import XhsStorageService
from app.services.xhs_workflow_service import XhsWorkflowService


def make_service(tmp_path):
    storage = XhsStorageService(
        evidence_root=tmp_path / ".local_evidence",
        archive_root=tmp_path / ".local_archive",
    )
    return XhsWorkflowService(
        registry=InMemoryXhsJobRegistry(),
        audit_log=AuditLogService(tmp_path / ".local_logs" / "xhs_audit.jsonl"),
        storage_service=storage,
        search_evidence_service=XhsEvidenceService(storage.evidence_root),
        publish_evidence_service=XhsPublishEvidenceService(storage.evidence_root),
        feishu_adapter=MockFeishuAdapter(),
        repository=InMemoryXhsRepository(),
    )


def request(keywords, workflow_id="wf-1", max_publish_jobs=2):
    return XhsSearchToPublishWorkflowRequest(
        workflow_id=workflow_id,
        account_id="xhs_dev_01",
        keywords=keywords,
        max_publish_jobs=max_publish_jobs,
    )


def test_workflow_success_writes_audit_and_registry(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_search_to_publish_mock_workflow(request(["眼影"]))

    assert result.status == "success"
    assert result.search_summary["success_count"] == 1
    assert result.publish_summary["success_count"] == 1
    assert service.registry.get_batch("wf-1")["status"] == "success"
    assert service.feishu_adapter.workflow_summaries[0]["workflow_id"] == "wf-1"
    assert service.repository.get_workflow_result("wf-1")["status"] == "success"
    assert (tmp_path / ".local_logs" / "xhs_audit.jsonl").exists()


def test_workflow_search_partial_failed(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_search_to_publish_mock_workflow(request(["眼影", "fail-search-粉底液"]))

    assert result.status == "XHS_WORKFLOW_PARTIAL_FAILED"
    assert result.search_summary["failed_count"] == 1
    assert result.publish_summary["success_count"] == 1


def test_workflow_publish_partial_failed(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_search_to_publish_mock_workflow(request(["眼影", "fail-publish-粉底液"]))

    assert result.status == "XHS_WORKFLOW_PARTIAL_FAILED"
    assert result.publish_summary["failed_count"] == 1


def test_workflow_no_normalized_records(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_search_to_publish_mock_workflow(request(["empty-keyword"]))

    assert result.status == "failed"
    assert result.error_code == "XHS_E2E_MOCK_FAILED"
    assert result.publish_summary["total_jobs"] == 0


def test_workflow_manifest_archived(tmp_path) -> None:
    service = make_service(tmp_path)

    result = service.run_search_to_publish_mock_workflow(request(["眼影"], workflow_id="wf-archive"))
    manifest_path = tmp_path / ".local_archive" / "xhs_workflow" / "wf-archive" / "manifest.json"

    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["workflow_id"] == "wf-archive"
    assert result.archived_files[-1]["status"] == "archived"
