from pathlib import Path

from app.providers.kuaijingvs_local_file_trigger import KuaJingVSLocalFileTriggerProvider
from app.schemas import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_WAITING_HUMAN_VERIFICATION,
    SearchJob,
)
from app.utils.errors import (
    KJVS_ENV_TIMEOUT,
    KJVS_OPEN_FAILED,
    KJVS_PROFILE_NOT_FOUND,
    LOCAL_RPA_EVIDENCE_INVALID,
    LOCAL_RPA_JOB_TIMEOUT,
    WorkerError,
)


def make_job() -> SearchJob:
    return SearchJob(
        job_id="local-file-provider-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger",
        keyword="眼影",
        limit=5,
    )


class FakeKuaJingVSService:
    def __init__(self, fail_step=None, open_result=None):
        self.fail_step = fail_step
        self.open_result = open_result or {"status": "success"}
        self.calls = []

    def resolve_shop_id(self, account_id):
        self.calls.append(("resolve_shop_id", account_id))
        if self.fail_step == "resolve":
            raise WorkerError(KJVS_PROFILE_NOT_FOUND, "profile not found")
        return "shop-123"

    def open_shop(self, shop_id):
        self.calls.append(("open_shop", shop_id))
        if self.fail_step == "open":
            raise WorkerError(KJVS_OPEN_FAILED, "open failed")
        return self.open_result

    def wait_environment_ready(self, shop_id):
        self.calls.append(("wait_environment_ready", shop_id))
        if self.fail_step == "wait":
            raise WorkerError(KJVS_ENV_TIMEOUT, "env timeout")
        return {"status": "ready"}

    def close_shop(self, shop_id):
        self.calls.append(("close_shop", shop_id))
        return {"status": "closed"}


class FakeQueueService:
    def __init__(self, tmp_path, evidence=None, fail_step=None):
        self.evidence_root = tmp_path / ".local_evidence"
        self.evidence = evidence or {
            "job_id": "local-file-provider-1",
            "status": "success",
            "message": "search completed",
            "screenshot_path": str(tmp_path / ".local_evidence" / "local-file-provider-1" / "xhs_search_smoke.png"),
            "items": [{"rank": 1, "title": "眼影"}],
            "normalized_records": [{"rank": 1, "keyword": "眼影"}],
        }
        self.fail_step = fail_step
        self.calls = []

    def enqueue_search_job(self, job, output_dir):
        self.calls.append(("enqueue_search_job", job.job_id, Path(output_dir)))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return Path(output_dir).parent.parent / ".local_rpa_jobs" / "pending" / f"{job.job_id}.json"

    def wait_for_evidence(self, evidence_json_path, timeout_seconds):
        self.calls.append(("wait_for_evidence", Path(evidence_json_path), timeout_seconds))
        if self.fail_step == "wait":
            raise WorkerError(LOCAL_RPA_JOB_TIMEOUT, "evidence timeout")
        return Path(evidence_json_path)

    def read_evidence(self, evidence_json_path):
        self.calls.append(("read_evidence", Path(evidence_json_path)))
        if self.fail_step == "read":
            raise WorkerError(LOCAL_RPA_EVIDENCE_INVALID, "invalid evidence")
        return self.evidence


def make_provider(tmp_path, kuaijingvs_service=None, queue_service=None, close_after_job=False):
    return KuaJingVSLocalFileTriggerProvider(
        kuaijingvs_service=kuaijingvs_service or FakeKuaJingVSService(),
        queue_service=queue_service or FakeQueueService(tmp_path),
        close_after_job=close_after_job,
        evidence_timeout_seconds=1,
    )


def test_local_file_trigger_provider_success_flow(tmp_path):
    kjvs = FakeKuaJingVSService()
    queue = FakeQueueService(tmp_path)
    provider = make_provider(tmp_path, kjvs, queue)

    result = provider.search(make_job())

    assert result.status == STATUS_SUCCESS
    assert result.job_id == "local-file-provider-1"
    assert result.screenshot_url.endswith("xhs_search_smoke.png")
    assert result.evidence_json_path.endswith("search_evidence.json")
    assert result.items == [{"rank": 1, "title": "眼影"}]
    assert result.normalized_records == [{"rank": 1, "keyword": "眼影"}]
    assert kjvs.calls == [
        ("resolve_shop_id", "xhs_dev_01"),
        ("open_shop", "shop-123"),
        ("wait_environment_ready", "shop-123"),
    ]
    assert [call[0] for call in queue.calls] == [
        "enqueue_search_job",
        "wait_for_evidence",
        "read_evidence",
    ]


def test_local_file_trigger_provider_profile_not_found(tmp_path):
    result = make_provider(
        tmp_path,
        kuaijingvs_service=FakeKuaJingVSService(fail_step="resolve"),
    ).search(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_PROFILE_NOT_FOUND


def test_local_file_trigger_provider_open_failed(tmp_path):
    result = make_provider(
        tmp_path,
        kuaijingvs_service=FakeKuaJingVSService(fail_step="open"),
    ).search(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_OPEN_FAILED


def test_local_file_trigger_provider_open_result_failed(tmp_path):
    result = make_provider(
        tmp_path,
        kuaijingvs_service=FakeKuaJingVSService(open_result={"status": "failed"}),
    ).search(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_OPEN_FAILED


def test_local_file_trigger_provider_env_timeout(tmp_path):
    result = make_provider(
        tmp_path,
        kuaijingvs_service=FakeKuaJingVSService(fail_step="wait"),
    ).search(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_ENV_TIMEOUT


def test_local_file_trigger_provider_evidence_timeout(tmp_path):
    result = make_provider(
        tmp_path,
        queue_service=FakeQueueService(tmp_path, fail_step="wait"),
    ).search(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == LOCAL_RPA_JOB_TIMEOUT


def test_local_file_trigger_provider_evidence_invalid(tmp_path):
    result = make_provider(
        tmp_path,
        queue_service=FakeQueueService(tmp_path, fail_step="read"),
    ).search(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == LOCAL_RPA_EVIDENCE_INVALID


def test_local_file_trigger_provider_waiting_human_verification(tmp_path):
    queue = FakeQueueService(
        tmp_path,
        evidence={
            "job_id": "local-file-provider-1",
            "status": STATUS_WAITING_HUMAN_VERIFICATION,
            "error_code": "WAITING_HUMAN_VERIFICATION",
            "error_message": "login or verification required",
        },
    )

    result = make_provider(tmp_path, queue_service=queue).search(make_job())

    assert result.status == STATUS_WAITING_HUMAN_VERIFICATION
    assert result.error_code == "WAITING_HUMAN_VERIFICATION"


def test_local_file_trigger_provider_close_after_job_true_on_failure(tmp_path):
    kjvs = FakeKuaJingVSService()
    queue = FakeQueueService(tmp_path, fail_step="wait")

    result = make_provider(tmp_path, kjvs, queue, close_after_job=True).search(make_job())

    assert result.status == STATUS_FAILED
    assert ("close_shop", "shop-123") in kjvs.calls


def test_local_file_trigger_provider_close_after_job_false(tmp_path):
    kjvs = FakeKuaJingVSService()

    result = make_provider(tmp_path, kuaijingvs_service=kjvs, close_after_job=False).search(make_job())

    assert result.status == STATUS_SUCCESS
    assert ("close_shop", "shop-123") not in kjvs.calls
