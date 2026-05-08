import json

import pytest

from app.schemas.search_job import SearchJob
from app.services.local_rpa_queue import LocalRpaQueueService
from app.utils.errors import (
    LOCAL_RPA_EVIDENCE_INVALID,
    LOCAL_RPA_JOB_TIMEOUT,
    WorkerError,
)


def make_job() -> SearchJob:
    return SearchJob(
        job_id="local-file-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger",
        keyword="眼影",
        limit=5,
    )


def make_queue(tmp_path) -> LocalRpaQueueService:
    return LocalRpaQueueService(
        queue_root=tmp_path / ".local_rpa_jobs",
        evidence_root=tmp_path / ".local_evidence",
        write_evidence_script_path=tmp_path / "scripts" / "write_yingdao_smoke_evidence.ps1",
    )


def test_ensure_dirs_creates_queue_state_dirs(tmp_path):
    queue = make_queue(tmp_path)

    queue.ensure_dirs()

    assert (queue.queue_root / "pending").exists()
    assert (queue.queue_root / "processing").exists()
    assert (queue.queue_root / "done").exists()
    assert (queue.queue_root / "failed").exists()


def test_build_search_payload_contains_expected_fields(tmp_path):
    queue = make_queue(tmp_path)
    output_dir = tmp_path / ".local_evidence" / "local-file-1"

    payload = queue.build_search_payload(make_job(), output_dir)

    assert payload["job_id"] == "local-file-1"
    assert payload["task_type"] == "xhs_keyword_search"
    assert payload["account_id"] == "xhs_dev_01"
    assert payload["provider_type"] == "kuaijingvs_local_file_trigger"
    assert payload["keyword"] == "眼影"
    assert payload["limit"] == 5
    assert payload["output_dir"] == str(output_dir)
    assert payload["before_scroll_screenshot_path"].endswith("xhs_search_before_scroll.png")
    assert payload["expected_screenshot_path"].endswith("xhs_search_smoke.png")
    assert payload["expected_evidence_json_path"].endswith("search_evidence.json")
    assert "powershell -NoProfile -ExecutionPolicy Bypass -File" in payload["dos_command"]
    assert "-Keyword \"眼影\"" in payload["dos_command"]
    assert payload["created_at"].endswith("Z")


def test_enqueue_search_job_writes_utf8_pending_json(tmp_path):
    queue = make_queue(tmp_path)
    output_dir = tmp_path / ".local_evidence" / "local-file-1"

    pending_path = queue.enqueue_search_job(make_job(), output_dir)
    raw_bytes = pending_path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))

    assert pending_path == queue.queue_root / "pending" / "local-file-1.json"
    assert raw_bytes[:3] != b"\xef\xbb\xbf"
    assert payload["keyword"] == "眼影"


def test_wait_for_evidence_success(tmp_path):
    queue = make_queue(tmp_path)
    evidence_path = tmp_path / "search_evidence.json"
    evidence_path.write_text("{}", encoding="utf-8")

    assert queue.wait_for_evidence(evidence_path, timeout_seconds=1) == evidence_path


def test_wait_for_evidence_timeout(tmp_path):
    queue = make_queue(tmp_path)

    with pytest.raises(WorkerError) as exc_info:
        queue.wait_for_evidence(tmp_path / "missing.json", timeout_seconds=0)

    assert exc_info.value.error_code == LOCAL_RPA_JOB_TIMEOUT


def test_read_evidence_success(tmp_path):
    queue = make_queue(tmp_path)
    evidence_path = tmp_path / "search_evidence.json"
    evidence_path.write_text(
        json.dumps({"status": "success", "keyword": "眼影"}, ensure_ascii=False),
        encoding="utf-8",
    )

    evidence = queue.read_evidence(evidence_path)

    assert evidence["status"] == "success"
    assert evidence["keyword"] == "眼影"


def test_read_evidence_invalid_json(tmp_path):
    queue = make_queue(tmp_path)
    evidence_path = tmp_path / "search_evidence.json"
    evidence_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(WorkerError) as exc_info:
        queue.read_evidence(evidence_path)

    assert exc_info.value.error_code == LOCAL_RPA_EVIDENCE_INVALID
