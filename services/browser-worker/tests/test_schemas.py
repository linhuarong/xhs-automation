from app.schemas import (
    STATUS_SUCCESS,
    PublishJob,
    SearchJob,
    WorkerResult,
)


def test_publish_job_default_provider_type() -> None:
    job = PublishJob(
        job_id="publish-test-1",
        account_id="xhs_dev_01",
        title="test title",
        body="test body",
        tags=["test"],
        images=[],
    )

    assert job.provider_type == "selenium_chrome"


def test_search_job_default_limit() -> None:
    job = SearchJob(
        job_id="search-test-1",
        account_id="xhs_dev_01",
        keyword="test keyword",
    )

    assert job.limit == 20


def test_worker_result_success_status() -> None:
    result = WorkerResult(
        job_id="result-test-1",
        status=STATUS_SUCCESS,
        evidence_json_path=".local_evidence/result-test-1/search_evidence.json",
    )

    assert result.status == "success"
    assert result.evidence_json_path == ".local_evidence/result-test-1/search_evidence.json"
