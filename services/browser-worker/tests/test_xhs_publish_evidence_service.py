import json

import pytest

from app.schemas import STATUS_FAILED, STATUS_SUCCESS, STATUS_WAITING_HUMAN_VERIFICATION
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService
from app.utils.errors import XHS_PUBLISH_EVIDENCE_INVALID, XHS_PUBLISH_EVIDENCE_NOT_FOUND, WorkerError


def test_ensure_publish_paths(tmp_path) -> None:
    paths = XhsPublishEvidenceService().ensure_publish_paths("publish-1", tmp_path)

    assert paths["output_dir"].exists()
    assert paths["expected_evidence_json_path"].name == "publish_evidence.json"
    assert paths["before_publish_screenshot_path"].name == "publish_before.png"
    assert paths["form_filled_screenshot_path"].name == "publish_form_filled.png"
    assert paths["result_screenshot_path"].name == "publish_result.png"


def test_write_and_read_publish_evidence_utf8_without_bom(tmp_path) -> None:
    service = XhsPublishEvidenceService()
    evidence_path = tmp_path / "publish_evidence.json"

    service.write_publish_evidence(
        {
            "job_id": "publish-1",
            "status": "success",
            "title": "中文标题",
            "result_screenshot_path": "publish_result.png",
        },
        evidence_path,
    )
    raw = evidence_path.read_bytes()
    evidence = service.read_publish_evidence(evidence_path)

    assert raw[:3] != b"\xef\xbb\xbf"
    assert json.loads(raw.decode("utf-8"))["title"] == "中文标题"
    assert evidence.title == "中文标题"


def test_read_publish_evidence_not_found(tmp_path) -> None:
    with pytest.raises(WorkerError) as exc:
        XhsPublishEvidenceService().read_publish_evidence(tmp_path / "missing.json")

    assert exc.value.error_code == XHS_PUBLISH_EVIDENCE_NOT_FOUND


def test_read_publish_evidence_invalid_json(tmp_path) -> None:
    evidence_path = tmp_path / "publish_evidence.json"
    evidence_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(WorkerError) as exc:
        XhsPublishEvidenceService().read_publish_evidence(evidence_path)

    assert exc.value.error_code == XHS_PUBLISH_EVIDENCE_INVALID


def test_map_publish_evidence_to_result_statuses() -> None:
    service = XhsPublishEvidenceService()

    success = service.map_evidence_to_result(
        {
            "job_id": "publish-1",
            "status": STATUS_SUCCESS,
            "note_url": "https://example.test/note",
            "result_screenshot_path": "publish_result.png",
        }
    )
    failed = service.map_evidence_to_result({"job_id": "publish-2", "status": STATUS_FAILED})
    waiting = service.map_evidence_to_result(
        {"job_id": "publish-3", "status": STATUS_WAITING_HUMAN_VERIFICATION}
    )

    assert success.status == STATUS_SUCCESS
    assert success.screenshot_url == "publish_result.png"
    assert failed.status == STATUS_FAILED
    assert waiting.status == STATUS_WAITING_HUMAN_VERIFICATION
