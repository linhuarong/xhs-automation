from app.integrations.postgres_repository import InMemoryXhsRepository


def test_in_memory_xhs_repository_publish_methods() -> None:
    repository = InMemoryXhsRepository()

    repository.save_publish_result({"job_id": "batch-1-publish-1", "batch_id": "batch-1", "status": "success"})
    repository.save_publish_result({"job_id": "batch-1-publish-2", "status": "failed"})

    assert repository.get_publish_job("batch-1-publish-1")["status"] == "success"
    assert len(repository.list_publish_jobs("batch-1")) == 2
