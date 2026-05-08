from app.providers.kuaijingvs_yingdao_rpa import KuaJingVSYingdaoRpaProvider
from app.schemas import STATUS_FAILED, STATUS_SUCCESS, STATUS_WAITING_HUMAN_VERIFICATION, SearchJob, WorkerResult
from app.utils.errors import (
    KJVS_ENV_TIMEOUT,
    KJVS_OPEN_FAILED,
    KJVS_PROFILE_NOT_FOUND,
    WorkerError,
)


class FakeKuaJingVSService:
    def __init__(
        self,
        resolve_error: WorkerError | None = None,
        open_error: WorkerError | None = None,
        ready_error: WorkerError | None = None,
        open_result: dict | None = None,
    ) -> None:
        self.resolve_error = resolve_error
        self.open_error = open_error
        self.ready_error = ready_error
        self.open_result = open_result or {"status": "opening"}
        self.calls: list[str] = []

    def resolve_shop_id(self, account_id: str) -> str:
        self.calls.append(f"resolve:{account_id}")
        if self.resolve_error is not None:
            raise self.resolve_error
        return "shop-123"

    def open_shop(self, shop_id: str) -> dict:
        self.calls.append(f"open:{shop_id}")
        if self.open_error is not None:
            raise self.open_error
        return self.open_result

    def wait_environment_ready(self, shop_id: str) -> dict:
        self.calls.append(f"wait:{shop_id}")
        if self.ready_error is not None:
            raise self.ready_error
        return {"status": "ready"}

    def close_shop(self, shop_id: str) -> dict:
        self.calls.append(f"close:{shop_id}")
        return {"status": "closed"}


class FakeYingdaoProvider:
    def __init__(self, result: WorkerResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def search(self, job: SearchJob) -> WorkerResult:
        self.calls.append(f"search:{job.job_id}")
        return self.result


def _search_job() -> SearchJob:
    return SearchJob(
        job_id="kjvs-yingdao-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_yingdao_rpa",
        keyword="\u773c\u5f71",
    )


def _result(status: str = STATUS_SUCCESS, error_code: str | None = None) -> WorkerResult:
    return WorkerResult(
        job_id="kjvs-yingdao-1",
        status=status,
        message="done" if status == STATUS_SUCCESS else None,
        error_code=error_code,
        error_message="error" if error_code else None,
        screenshot_url="shot.png",
        evidence_json_path="evidence.json",
        items=[{"rank": 1}],
        normalized_records=[{"rank": 1}],
    )


def test_success_flow_calls_kjvs_then_yingdao() -> None:
    kjvs = FakeKuaJingVSService()
    yingdao = FakeYingdaoProvider(_result())
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=kjvs,
        yingdao_provider=yingdao,
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_SUCCESS
    assert result.evidence_json_path == "evidence.json"
    assert kjvs.calls == ["resolve:xhs_dev_01", "open:shop-123", "wait:shop-123"]
    assert yingdao.calls == ["search:kjvs-yingdao-1"]


def test_profile_not_found_returns_failed() -> None:
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=FakeKuaJingVSService(
            resolve_error=WorkerError(
                error_code=KJVS_PROFILE_NOT_FOUND,
                error_message="profile missing",
            )
        ),
        yingdao_provider=FakeYingdaoProvider(_result()),
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_PROFILE_NOT_FOUND
    assert result.error_message == "profile missing"


def test_open_failed_worker_error_returns_failed() -> None:
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=FakeKuaJingVSService(
            open_error=WorkerError(
                error_code=KJVS_OPEN_FAILED,
                error_message="open failed",
            )
        ),
        yingdao_provider=FakeYingdaoProvider(_result()),
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_OPEN_FAILED
    assert result.error_message == "open failed"


def test_open_failed_result_returns_failed() -> None:
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=FakeKuaJingVSService(
            open_result={"status": "failed", "error_message": "open failed"}
        ),
        yingdao_provider=FakeYingdaoProvider(_result()),
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_OPEN_FAILED
    assert "open failed" in result.error_message


def test_env_timeout_returns_failed() -> None:
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=FakeKuaJingVSService(
            ready_error=WorkerError(
                error_code=KJVS_ENV_TIMEOUT,
                error_message="env timeout",
            )
        ),
        yingdao_provider=FakeYingdaoProvider(_result()),
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_ENV_TIMEOUT


def test_yingdao_waiting_human_result_is_returned_as_is() -> None:
    delegate_result = _result(
        status=STATUS_WAITING_HUMAN_VERIFICATION,
        error_code="WAITING_HUMAN_VERIFICATION",
    )
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=FakeKuaJingVSService(),
        yingdao_provider=FakeYingdaoProvider(delegate_result),
    )

    result = provider.search(_search_job())

    assert result is delegate_result
    assert result.status == STATUS_WAITING_HUMAN_VERIFICATION


def test_yingdao_failed_result_is_returned_as_is() -> None:
    delegate_result = _result(status=STATUS_FAILED, error_code="YINGDAO_JOB_FAILED")
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=FakeKuaJingVSService(),
        yingdao_provider=FakeYingdaoProvider(delegate_result),
    )

    result = provider.search(_search_job())

    assert result is delegate_result
    assert result.status == STATUS_FAILED


def test_close_after_job_closes_even_when_yingdao_failed() -> None:
    kjvs = FakeKuaJingVSService()
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=kjvs,
        yingdao_provider=FakeYingdaoProvider(
            _result(status=STATUS_FAILED, error_code="YINGDAO_JOB_FAILED")
        ),
        close_after_job=True,
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_FAILED
    assert kjvs.calls == [
        "resolve:xhs_dev_01",
        "open:shop-123",
        "wait:shop-123",
        "close:shop-123",
    ]


def test_close_after_job_false_does_not_close() -> None:
    kjvs = FakeKuaJingVSService()
    provider = KuaJingVSYingdaoRpaProvider(
        kuaijingvs_service=kjvs,
        yingdao_provider=FakeYingdaoProvider(_result()),
        close_after_job=False,
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_SUCCESS
    assert "close:shop-123" not in kjvs.calls
