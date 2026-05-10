from app.integrations.feishu_adapter import MockFeishuAdapter


def test_mock_feishu_adapter_publish_methods() -> None:
    adapter = MockFeishuAdapter()

    result = adapter.upsert_publish_result({"job_id": "publish-1", "status": "success"})
    summary = adapter.upsert_publish_batch_summary({"batch_id": "batch-1", "success_count": 1})
    attachment = adapter.attach_publish_evidence("publish-1", [{"name": "publish_evidence.json"}])

    assert result["status"] == "success"
    assert summary["summary"]["batch_id"] == "batch-1"
    assert attachment["job_id"] == "publish-1"
    assert adapter.publish_results == [{"job_id": "publish-1", "status": "success"}]
    assert adapter.publish_batch_summaries == [{"batch_id": "batch-1", "success_count": 1}]
    assert adapter.publish_evidence_attachments[0]["files"] == [{"name": "publish_evidence.json"}]
