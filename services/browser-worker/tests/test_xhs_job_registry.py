from app.services.xhs_job_registry import InMemoryXhsJobRegistry


def test_register_get_and_update_job() -> None:
    registry = InMemoryXhsJobRegistry()

    registry.register_job("job-1", "search", {"keyword": "眼影"})
    registry.update_job_status("job-1", "success", {"evidence_json_path": "search_evidence.json"})
    job = registry.get_job("job-1")

    assert job["status"] == "success"
    assert job["payload"]["keyword"] == "眼影"
    assert job["result"]["evidence_json_path"] == "search_evidence.json"


def test_batch_register_list_and_get() -> None:
    registry = InMemoryXhsJobRegistry()

    registry.register_job("batch-1-job-1", "search", {"batch_id": "batch-1"})
    registry.register_batch("batch-1", "search", ["batch-1-job-1"])
    registry.update_batch_summary("batch-1", {"status": "success", "success_count": 1})

    assert registry.get_batch("batch-1")["summary"]["success_count"] == 1
    assert len(registry.list_jobs("batch-1")) == 1


def test_registry_not_found_markers() -> None:
    registry = InMemoryXhsJobRegistry()

    assert registry.get_job("missing")["status"] == "not_found"
    assert registry.get_batch("missing")["status"] == "not_found"
