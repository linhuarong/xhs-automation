import json

from app.providers import get_provider
from app.providers.yingdao_local_file_trigger import YingdaoLocalFileTriggerProvider
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService


def test_provider_registered() -> None:
    provider = get_provider("yingdao_local_file_trigger")

    assert isinstance(provider, YingdaoLocalFileTriggerProvider)
    assert provider.provider_type == "yingdao_local_file_trigger"


def test_provider_prepare_search_returns_accepted(tmp_path) -> None:
    provider = YingdaoLocalFileTriggerProvider(
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    )

    result = provider.prepare_search(
        {
            "job_id": "search-local-001",
            "account_id": "xhs_dev_01",
            "keyword": "眼影",
            "limit": 20,
        }
    )

    assert result.status == "accepted"
    assert result.evidence_json_path.endswith("search_evidence.json")


def test_provider_prepare_publish_returns_accepted(tmp_path) -> None:
    provider = YingdaoLocalFileTriggerProvider(
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    )

    result = provider.prepare_publish(
        {
            "job_id": "publish-local-001",
            "account_id": "xhs_dev_01",
            "title": "测试标题",
            "body": "测试正文",
            "tags": ["眼影"],
            "image_paths": [],
        }
    )

    assert result.status == "accepted"
    assert result.evidence_json_path.endswith("publish_evidence.json")


def test_provider_read_search_result_waiting_when_missing(tmp_path) -> None:
    provider = YingdaoLocalFileTriggerProvider(
        YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    )

    result = provider.read_search_result("search-local-001")

    assert result.status == "waiting_rpa_result"


def test_provider_read_publish_result_success_from_mock_evidence(tmp_path) -> None:
    service = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    job_dir = tmp_path / "queue" / "publish" / "jobs" / "publish-local-001"
    job_dir.mkdir(parents=True)
    (job_dir / "publish_evidence.json").write_text(
        json.dumps(
            {
                "job_id": "publish-local-001",
                "job_type": "xhs_publish",
                "status": "waiting_manual_review",
                "message": "prepared",
            }
        ),
        encoding="utf-8",
    )
    provider = YingdaoLocalFileTriggerProvider(service)

    result = provider.read_publish_result("publish-local-001")

    assert result.status == "waiting_manual_review"
    assert result.message == "prepared"
