import json

from app.schemas import XhsPublishAsset, XhsPublishJob
from app.services.local_rpa_queue import LocalRpaQueueService


def make_publish_job() -> XhsPublishJob:
    return XhsPublishJob(
        job_id="publish-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger_publish",
        title="中文标题",
        body="正文",
        tags=["眼影", "彩妆"],
        assets=[XhsPublishAsset(local_path="image.png", order=1)],
    )


def make_queue(tmp_path) -> LocalRpaQueueService:
    return LocalRpaQueueService(
        queue_root=tmp_path / ".local_rpa_jobs",
        evidence_root=tmp_path / ".local_evidence",
        write_publish_evidence_script_path=tmp_path / "scripts" / "write_xhs_publish_evidence.ps1",
    )


def test_build_publish_payload_contains_expected_fields(tmp_path) -> None:
    queue = make_queue(tmp_path)
    output_dir = tmp_path / ".local_evidence" / "publish-1"

    payload = queue.build_publish_payload(make_publish_job(), output_dir)

    assert payload["job_id"] == "publish-1"
    assert payload["task_type"] == "xhs_publish_note"
    assert payload["title"] == "中文标题"
    assert payload["body"] == "正文"
    assert payload["tags"] == ["眼影", "彩妆"]
    assert payload["assets"][0]["local_path"] == "image.png"
    assert payload["expected_evidence_json_path"].endswith("publish_evidence.json")
    assert payload["before_publish_screenshot_path"].endswith("publish_before.png")
    assert payload["form_filled_screenshot_path"].endswith("publish_form_filled.png")
    assert payload["result_screenshot_path"].endswith("publish_result.png")
    assert "write_xhs_publish_evidence.ps1" in payload["dos_command"]


def test_enqueue_publish_job_writes_active_publish_job_and_trigger(tmp_path) -> None:
    queue = make_queue(tmp_path)
    output_dir = tmp_path / ".local_evidence" / "publish-1"

    active_job_path = queue.enqueue_publish_job(make_publish_job(), output_dir)
    trigger_path = queue.queue_root / "pending" / "_trigger_publish_publish-1.trigger"
    raw_bytes = active_job_path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))

    assert active_job_path == queue.queue_root / "pending" / "_active_publish_job.json"
    assert trigger_path.exists()
    assert trigger_path.read_text(encoding="utf-8") == "publish-1"
    assert raw_bytes[:3] != b"\xef\xbb\xbf"
    assert payload["title"] == "中文标题"
    assert payload["dos_command"]
