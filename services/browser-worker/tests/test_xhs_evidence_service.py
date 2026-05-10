import json

import pytest

from app.services.xhs_evidence_service import XhsEvidenceService
from app.utils.errors import XHS_EVIDENCE_INVALID, WorkerError


def test_normalize_empty_items() -> None:
    service = XhsEvidenceService()

    evidence = service.normalize_evidence({"job_id": "job-1", "items": []})

    assert evidence.item_count == 0
    assert evidence.normalized_record_count == 0
    assert evidence.normalized_records == []


def test_normalize_items_when_records_missing() -> None:
    service = XhsEvidenceService()

    evidence = service.normalize_evidence(
        {
            "job_id": "job-1",
            "keyword": "眼影",
            "account_id": "xhs_dev_01",
            "provider_type": "kuaijingvs_local_file_trigger",
            "screenshot_path": "xhs_search_smoke.png",
            "items": [
                {
                    "title": "新手眼影",
                    "like_count": "1.2万",
                    "collect_count": "3K",
                    "comment_count": "1,234",
                }
            ],
        }
    )

    record = evidence.normalized_records[0]
    assert record.rank == 1
    assert record.keyword == "眼影"
    assert record.like_count == 12000
    assert record.collect_count == 3000
    assert record.comment_count == 1234
    assert record.engagement_score == 12000 + 3000 * 1.5 + 1234 * 2


def test_existing_normalized_records_are_preserved() -> None:
    service = XhsEvidenceService()

    evidence = service.normalize_evidence(
        {
            "job_id": "job-1",
            "items": [{"title": "raw"}],
            "normalized_records": [{"job_id": "job-1", "rank": 99, "title": "kept"}],
        }
    )

    assert evidence.normalized_records[0].rank == 99
    assert evidence.normalized_records[0].title == "kept"
    assert evidence.normalized_record_count == 1


def test_parse_count_formats() -> None:
    service = XhsEvidenceService()

    assert service.parse_count("188") == 188
    assert service.parse_count("1.2万") == 12000
    assert service.parse_count("3k") == 3000
    assert service.parse_count("3K") == 3000
    assert service.parse_count("1,234") == 1234
    assert service.parse_count("bad") == 0


def test_read_invalid_json_raises(tmp_path) -> None:
    evidence_path = tmp_path / "search_evidence.json"
    evidence_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(WorkerError) as exc:
        XhsEvidenceService().read_evidence(evidence_path)

    assert exc.value.error_code == XHS_EVIDENCE_INVALID


def test_write_normalized_evidence_utf8_without_bom(tmp_path) -> None:
    evidence_path = tmp_path / "search_evidence.json"
    service = XhsEvidenceService()

    service.write_normalized_evidence(
        {
            "job_id": "job-1",
            "keyword": "眼影",
            "items": [{"title": "中文标题", "like_count": "188"}],
        },
        evidence_path,
    )
    raw = evidence_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))

    assert raw[:3] != b"\xef\xbb\xbf"
    assert payload["normalized_record_count"] == 1
    assert payload["items"][0]["title"] == "中文标题"


def test_ensure_evidence_paths(tmp_path) -> None:
    paths = XhsEvidenceService().ensure_evidence_paths("job-1", tmp_path)

    assert paths["output_dir"].exists()
    assert paths["expected_evidence_json_path"].name == "search_evidence.json"
    assert paths["expected_screenshot_path"].name == "xhs_search_smoke.png"
    assert paths["before_scroll_screenshot_path"].name == "xhs_search_before_scroll.png"
