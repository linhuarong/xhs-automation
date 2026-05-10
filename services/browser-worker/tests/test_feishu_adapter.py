from app.integrations.feishu_adapter import MockFeishuAdapter


def test_mock_feishu_adapter_receives_records() -> None:
    adapter = MockFeishuAdapter()

    result = adapter.upsert_keyword_result({"job_id": "job-1", "keyword": "眼影"})
    summary = adapter.upsert_batch_summary({"batch_id": "batch-1", "success_count": 1})
    attachment = adapter.attach_evidence("job-1", [{"name": "search_evidence.json"}])

    assert result["status"] == "success"
    assert summary["status"] == "success"
    assert attachment["job_id"] == "job-1"
    assert adapter.keyword_results == [{"job_id": "job-1", "keyword": "眼影"}]
    assert adapter.batch_summaries == [{"batch_id": "batch-1", "success_count": 1}]
    assert adapter.evidence_attachments[0]["files"] == [{"name": "search_evidence.json"}]
