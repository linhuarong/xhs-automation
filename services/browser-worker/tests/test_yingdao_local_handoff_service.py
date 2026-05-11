import json

from app.schemas import SearchJob
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import XHS_YINGDAO_EVIDENCE_INVALID, XHS_YINGDAO_EVIDENCE_NOT_FOUND


def test_prepare_search_handoff_writes_active_job_snapshot_and_manifest(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)

    result = service.prepare_search_handoff(
        SearchJob(
            job_id="search-local-001",
            account_id="xhs_dev_01",
            provider_type="yingdao_local_file_trigger",
            keyword="眼影",
            limit=20,
        )
    )

    active_path = tmp_path / "queue" / "search" / "_active_job.json"
    job_path = tmp_path / "queue" / "search" / "jobs" / "search-local-001" / "job.json"
    manifest_path = tmp_path / "queue" / "search" / "jobs" / "search-local-001" / "handoff_manifest.json"
    assert result.status == "accepted"
    assert active_path.exists()
    assert job_path.exists()
    assert manifest_path.exists()
    active = json.loads(active_path.read_text(encoding="utf-8"))
    assert active["keyword"] == "眼影"
    assert active["limit"] == 20
    assert active["evidence_output_dir"]
    assert active["instructions"]["do_not_bypass_login_or_verification"] is True


def test_prepare_publish_handoff_writes_tags_and_image_paths_json(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)

    result = service.prepare_publish_handoff(
        {
            "job_id": "publish-local-001",
            "account_id": "xhs_dev_01",
            "provider_type": "yingdao_local_file_trigger",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影", "美妆"],
            "image_paths": [r".local_assets\publish-local-001\01.png"],
        }
    )

    active_path = tmp_path / "queue" / "publish" / "_active_publish_job.json"
    active_bytes = active_path.read_bytes()
    assert active_bytes.startswith(b"{")
    active = json.loads(active_bytes.decode("utf-8"))
    assert result.status == "accepted"
    assert active["title"] == "测试标题"
    assert active["body"] == "测试正文"
    assert json.loads(active["tags_json"]) == ["眼影", "美妆"]
    assert json.loads(active["image_paths_json"]) == [r".local_assets\publish-local-001\01.png"]
    assert active["instructions"]["do_not_click_final_publish_without_manual_review"] is True


def test_read_search_evidence_missing_returns_waiting(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)

    result = service.read_search_evidence("missing-job")

    assert result.status == "waiting_rpa_result"
    assert result.error_code == XHS_YINGDAO_EVIDENCE_NOT_FOUND


def test_read_publish_evidence_missing_returns_waiting(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)

    result = service.read_publish_evidence("missing-job")

    assert result.status == "waiting_rpa_result"
    assert result.error_code == XHS_YINGDAO_EVIDENCE_NOT_FOUND


def test_mock_search_evidence_converts_to_worker_result(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    job_dir = tmp_path / "queue" / "search" / "jobs" / "search-local-001"
    job_dir.mkdir(parents=True)
    (job_dir / "search_evidence.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": "search-local-001",
                "job_type": "xhs_search",
                "status": "success",
                "keyword": "眼影",
                "items": [],
                "normalized_records": [],
                "screenshot_path": "search_success.png",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = service.read_search_evidence("search-local-001")

    assert result.status == "success"
    assert result.worker_result["job_id"] == "search-local-001"
    assert result.worker_result["screenshot_url"] == "search_success.png"


def test_mock_publish_evidence_converts_to_worker_result(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    job_dir = tmp_path / "queue" / "publish" / "jobs" / "publish-local-001"
    job_dir.mkdir(parents=True)
    (job_dir / "publish_evidence.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": "publish-local-001",
                "job_type": "xhs_publish",
                "status": "waiting_manual_review",
                "title": "测试标题",
                "message": "publish form prepared, waiting manual review",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = service.read_publish_evidence("publish-local-001")

    assert result.status == "waiting_manual_review"
    assert result.worker_result["status"] == "waiting_manual_review"


def test_invalid_evidence_returns_invalid_error(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    job_dir = tmp_path / "queue" / "search" / "jobs" / "bad-job"
    job_dir.mkdir(parents=True)
    (job_dir / "search_evidence.json").write_text("{bad", encoding="utf-8")

    result = service.read_search_evidence("bad-job")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_EVIDENCE_INVALID


def test_get_active_job_status_is_shallow(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    service.prepare_search_handoff(
        {
            "job_id": "search-local-001",
            "account_id": "xhs_dev_01",
            "keyword": "眼影",
            "limit": 20,
        }
    )

    status = service.get_active_job_status()

    assert status["search"]["exists"] is True
    assert status["search"]["job_id"] == "search-local-001"
    assert "keyword" not in status["search"]
