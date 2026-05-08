import pytest

from app.services.yingdao_service import YingdaoService


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
    service = YingdaoService(http_client=client)

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
    service = YingdaoService(http_client=client)

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

    with pytest.raises(TimeoutError, match="timed out"):
        service.wait_job_done("job-1", timeout_seconds=0)


def test_wait_job_done_failed_raises_clear_error(monkeypatch) -> None:
    service = YingdaoService(http_client=FakeHttpClient(), poll_interval_seconds=0)
    monkeypatch.setattr(
        service,
        "query_job",
        lambda job_uuid: {"status": "failed", "error_message": "rpa failed"},
    )

    with pytest.raises(RuntimeError, match="rpa failed"):
        service.wait_job_done("job-1", timeout_seconds=5)


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
