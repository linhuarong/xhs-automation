import pytest

from app.services.yingdao_service import YingdaoService
from app.utils.errors import (
    YINGDAO_CONFIG_ERROR,
    YINGDAO_JOB_FAILED,
    YINGDAO_JOB_TIMEOUT,
    WorkerError,
)


class FakeHttpClient:
    def __init__(self) -> None:
        self.post_responses: list[dict] = []
        self.get_responses: list[dict] = []
        self.posts: list[tuple[str, dict, dict | None]] = []
        self.gets: list[tuple[str, dict | None]] = []

    def post_json(self, url: str, payload: dict, headers: dict | None = None) -> dict:
        self.posts.append((url, payload, headers))
        return self.post_responses.pop(0)

    def get_json(self, url: str, headers: dict | None = None) -> dict:
        self.gets.append((url, headers))
        return self.get_responses.pop(0)


def test_get_access_token_uses_mock_client() -> None:
    client = FakeHttpClient()
    client.post_responses.append({"access_token": "token-1"})
    service = YingdaoService(
        access_key_id="key",
        access_key_secret="secret",
        http_client=client,
    )

    assert service.get_access_token() == "token-1"
    assert client.posts[0][1] == {
        "access_key_id": "key",
        "access_key_secret": "secret",
    }


def test_start_job_uses_mock_client() -> None:
    client = FakeHttpClient()
    client.post_responses.extend([{"access_token": "token-1"}, {"job_uuid": "job-1"}])
    service = YingdaoService(
        access_key_id="key",
        access_key_secret="secret",
        account_name="account",
        robot_uuid="robot",
        http_client=client,
    )

    result = service.start_job(
        account_name="account",
        robot_uuid="robot",
        params=[{"name": "keyword", "value": "\u773c\u5f71"}],
    )

    assert result == {"job_uuid": "job-1"}
    assert client.posts[1][1]["account_name"] == "account"
    assert client.posts[1][2] == {"Authorization": "Bearer token-1"}


def test_query_job_uses_mock_client() -> None:
    client = FakeHttpClient()
    client.post_responses.append({"access_token": "token-1"})
    client.get_responses.append({"status": "success"})
    service = YingdaoService(access_key_id="key", access_key_secret="secret", http_client=client)

    assert service.query_job("job-1") == {"status": "success"}
    assert client.gets[0][0].endswith("/openapi/jobs/job-1")


def test_wait_job_done_success(monkeypatch) -> None:
    service = YingdaoService(http_client=FakeHttpClient(), poll_interval_seconds=0)
    responses = [{"status": "running"}, {"status": "success", "outputs": {"a": 1}}]
    monkeypatch.setattr(service, "query_job", lambda job_uuid: responses.pop(0))

    assert service.wait_job_done("job-1", timeout_seconds=5) == {
        "status": "success",
        "outputs": {"a": 1},
    }


def test_wait_job_done_timeout(monkeypatch) -> None:
    service = YingdaoService(http_client=FakeHttpClient(), poll_interval_seconds=0)
    monkeypatch.setattr(service, "query_job", lambda job_uuid: {"status": "running"})

    with pytest.raises(WorkerError) as exc:
        service.wait_job_done("job-1", timeout_seconds=0)
    assert exc.value.error_code == YINGDAO_JOB_TIMEOUT
    assert "timed out" in exc.value.error_message


def test_wait_job_done_failed_raises_clear_error(monkeypatch) -> None:
    service = YingdaoService(http_client=FakeHttpClient(), poll_interval_seconds=0)
    monkeypatch.setattr(
        service,
        "query_job",
        lambda job_uuid: {"status": "failed", "error_message": "rpa failed"},
    )

    with pytest.raises(WorkerError) as exc:
        service.wait_job_done("job-1", timeout_seconds=5)
    assert exc.value.error_code == YINGDAO_JOB_FAILED
    assert "rpa failed" in exc.value.error_message


def test_extract_outputs_maps_evidence_fields() -> None:
    service = YingdaoService(http_client=FakeHttpClient())

    outputs = service.extract_outputs(
        {
            "outputs": [
                {"name": "evidence_json_path", "value": "evidence.json"},
                {"name": "output_dir", "value": "out"},
            ]
        }
    )

    assert outputs["evidence_json_path"] == "evidence.json"
    assert outputs["output_dir"] == "out"


def test_start_job_missing_config_raises_worker_error() -> None:
    service = YingdaoService(http_client=FakeHttpClient())

    with pytest.raises(WorkerError) as exc:
        service.start_job(account_name="", robot_uuid="", params=[])

    assert exc.value.error_code == YINGDAO_CONFIG_ERROR
    assert "YINGDAO_ACCESS_KEY_ID" in exc.value.error_message
    assert "YINGDAO_ACCESS_KEY_SECRET" in exc.value.error_message
    assert "YINGDAO_ACCOUNT_NAME" in exc.value.error_message
    assert "YINGDAO_ROBOT_UUID" in exc.value.error_message


def test_invalid_poll_interval_env_raises_config_error(monkeypatch) -> None:
    monkeypatch.setenv("YINGDAO_JOB_POLL_INTERVAL_SECONDS", "not-int")

    with pytest.raises(WorkerError) as exc:
        YingdaoService(http_client=FakeHttpClient())

    assert exc.value.error_code == YINGDAO_CONFIG_ERROR
    assert "YINGDAO_JOB_POLL_INTERVAL_SECONDS" in exc.value.error_message


def test_extract_outputs_supports_multiple_output_names() -> None:
    service = YingdaoService(http_client=FakeHttpClient())

    outputs = service.extract_outputs(
        {
            "status": "success",
            "outputs": {
                "search_evidence_json": "search_evidence.json",
                "evidence_output_dir": "evidence-dir",
                "screenshot_path": "shot.png",
            },
        }
    )

    assert outputs["evidence_json_path"] == "search_evidence.json"
    assert outputs["evidence_output_dir"] == "evidence-dir"
    assert outputs["screenshot_path"] == "shot.png"
    assert outputs["status"] == "success"


def test_extract_outputs_missing_fields_returns_empty_dict() -> None:
    service = YingdaoService(http_client=FakeHttpClient())

    assert service.extract_outputs({"outputs": None}) == {}
