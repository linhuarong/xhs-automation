from app.integrations.postgres_repository import InMemoryXhsRepository


def test_in_memory_xhs_repository_save_get_list() -> None:
    repository = InMemoryXhsRepository()

    repository.save_job_result({"job_id": "batch-1-眼影-1", "batch_id": "batch-1", "status": "success"})
    repository.save_job_result({"job_id": "batch-1-粉底液-2", "status": "failed"})
    records = repository.save_normalized_records([{"job_id": "batch-1-眼影-1", "rank": 1}])
    workflow = repository.save_workflow_result({"workflow_id": "wf-1", "status": "success"})

    assert repository.get_job("batch-1-眼影-1")["status"] == "success"
    assert len(repository.list_jobs("batch-1")) == 2
    assert records == [{"job_id": "batch-1-眼影-1", "rank": 1}]
    assert repository.normalized_records == [{"job_id": "batch-1-眼影-1", "rank": 1}]
    assert workflow["workflow_id"] == "wf-1"
    assert repository.get_workflow_result("wf-1")["status"] == "success"
