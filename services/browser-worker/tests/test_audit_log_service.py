import json

import pytest

from app.services.audit_log_service import AuditLogService
from app.utils.errors import XHS_AUDIT_LOG_ERROR, WorkerError


def test_audit_log_writes_jsonl_and_preserves_chinese(tmp_path) -> None:
    log_path = tmp_path / "xhs_audit.jsonl"
    service = AuditLogService(log_path)

    service.append_event("search_job_created", job_id="job-1", status="pending", payload={"keyword": "眼影"})
    service.append_event("search_job_completed", job_id="job-1", status="success", message="完成")

    raw = log_path.read_bytes()
    lines = log_path.read_text(encoding="utf-8").splitlines()

    assert raw[:3] != b"\xef\xbb\xbf"
    assert len(lines) == 2
    assert json.loads(lines[0])["payload"]["keyword"] == "眼影"
    assert json.loads(lines[1])["message"] == "完成"


def test_audit_log_invalid_path_has_clear_error(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    service = AuditLogService(blocker / "xhs_audit.jsonl")

    with pytest.raises(WorkerError) as exc:
        service.append_event("batch_created")

    assert exc.value.error_code == XHS_AUDIT_LOG_ERROR
