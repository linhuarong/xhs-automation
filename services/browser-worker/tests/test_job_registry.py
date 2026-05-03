from app.services import JobRegistry


def test_job_registry_create_update_get_list() -> None:
    registry = JobRegistry()

    created = registry.create_job(
        job_id="registry-test-1",
        task_type="keyword_search",
    )
    updated = registry.update_job(
        "registry-test-1",
        status="success",
        current_step="done",
        message="job completed",
    )
    found = registry.get_job("registry-test-1")
    jobs = registry.list_jobs()

    assert created.job_id == "registry-test-1"
    assert created.task_type == "keyword_search"
    assert updated.status == "success"
    assert updated.current_step == "done"
    assert updated.message == "job completed"
    assert found is updated
    assert updated in jobs
