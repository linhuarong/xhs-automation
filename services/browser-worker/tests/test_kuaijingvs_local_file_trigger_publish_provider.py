from pathlib import Path

from app.providers.kuaijingvs_local_file_trigger_publish import KuaJingVSLocalFileTriggerPublishProvider
from app.schemas import STATUS_FAILED, STATUS_SUCCESS, STATUS_WAITING_HUMAN_VERIFICATION, XhsPublishJob
from app.services.xhs_publish_evidence_service import XhsPublishEvidenceService
from app.utils.errors import (
    KJVS_OPEN_FAILED,
    LOCAL_RPA_JOB_TIMEOUT,
    XHS_PUBLISH_EVIDENCE_INVALID,
    XHS_PUBLISH_EVIDENCE_TIMEOUT,
    WorkerError,
)


def make_job() -> XhsPublishJob:
    return XhsPublishJob(
        job_id="publish-provider-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger_publish",
        title="标题",
        body="正文",
    )


class FakeKuaJingVSService:
    def __init__(self, fail_step=None, open_result=None):
        self.fail_step = fail_step
        self.open_result = open_result or {"status": "success"}
        self.calls = []

    def resolve_shop_id(self, account_id):
        self.calls.append(("resolve_shop_id", account_id))
        return "shop-123"

    def open_shop(self, shop_id):
        self.calls.append(("open_shop", shop_id))
        if self.fail_step == "open":
            raise WorkerError(KJVS_OPEN_FAILED, "open failed")
        return self.open_result

    def close_shop(self, shop_id):
        self.calls.append(("close_shop", shop_id))
        return {"status": "closed"}


class FakeQueueService:
    def __init__(self, tmp_path, fail_step=None):
        self.evidence_root = tmp_path / ".local_evidence"
        self.fail_step = fail_step
        self.calls = []

    def enqueue_publish_job(self, job, output_dir):
        self.calls.append(("enqueue_publish_job", job.job_id, Path(output_dir)))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return Path(output_dir).parent.parent / ".local_rpa_jobs" / "pending" / "_active_publish_job.json"

    def wait_for_evidence(self, evidence_json_path, timeout_seconds):
        self.calls.append(("wait_for_evidence", Path(evidence_json_path), timeout_seconds))
        if self.fail_step == "wait":
            raise WorkerError(LOCAL_RPA_JOB_TIMEOUT, "evidence timeout")
        return Path(evidence_json_path)


class FakeEvidenceService:
    def __init__(self, status=STATUS_SUCCESS, fail_read=False):
        self.status = status
        self.fail_read = fail_read
        self.calls = []

    def read_publish_evidence(self, evidence_path):
        self.calls.append(("read_publish_evidence", Path(evidence_path)))
        if self.fail_read:
            raise WorkerError(XHS_PUBLISH_EVIDENCE_INVALID, "invalid evidence")
        return {
            "job_id": "publish-provider-1",
            "status": self.status,
            "evidence_json_path": str(evidence_path),
            "result_screenshot_path": str(Path(evidence_path).with_name("publish_result.png")),
        }

    def map_evidence_to_result(self, evidence):
        return XhsPublishEvidenceService().map_evidence_to_result(evidence)


def make_provider(tmp_path, kjvs=None, queue=None, evidence=None, close_after_job=False):
    return KuaJingVSLocalFileTriggerPublishProvider(
        kuaijingvs_service=kjvs or FakeKuaJingVSService(),
        queue_service=queue or FakeQueueService(tmp_path),
        evidence_service=evidence or FakeEvidenceService(),
        close_after_job=close_after_job,
        evidence_timeout_seconds=1,
    )


def test_publish_provider_success_flow_enqueues_after_open(tmp_path) -> None:
    kjvs = FakeKuaJingVSService()
    queue = FakeQueueService(tmp_path)
    provider = make_provider(tmp_path, kjvs=kjvs, queue=queue)

    result = provider.publish(make_job())

    assert result.status == STATUS_SUCCESS
    assert result.evidence_json_path.endswith("publish_evidence.json")
    assert kjvs.calls == [("resolve_shop_id", "xhs_dev_01"), ("open_shop", "shop-123")]
    assert queue.calls[0][0] == "enqueue_publish_job"


def test_publish_provider_open_failed(tmp_path) -> None:
    result = make_provider(tmp_path, kjvs=FakeKuaJingVSService(fail_step="open")).publish(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_OPEN_FAILED


def test_publish_provider_open_result_failed(tmp_path) -> None:
    result = make_provider(tmp_path, kjvs=FakeKuaJingVSService(open_result={"status": "failed"})).publish(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == KJVS_OPEN_FAILED


def test_publish_provider_evidence_timeout(tmp_path) -> None:
    result = make_provider(tmp_path, queue=FakeQueueService(tmp_path, fail_step="wait")).publish(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == XHS_PUBLISH_EVIDENCE_TIMEOUT


def test_publish_provider_evidence_invalid(tmp_path) -> None:
    result = make_provider(tmp_path, evidence=FakeEvidenceService(fail_read=True)).publish(make_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == XHS_PUBLISH_EVIDENCE_INVALID


def test_publish_provider_waiting_human_verification(tmp_path) -> None:
    result = make_provider(tmp_path, evidence=FakeEvidenceService(status=STATUS_WAITING_HUMAN_VERIFICATION)).publish(
        make_job()
    )

    assert result.status == STATUS_WAITING_HUMAN_VERIFICATION


def test_publish_provider_close_after_job_true(tmp_path) -> None:
    kjvs = FakeKuaJingVSService()

    make_provider(tmp_path, kjvs=kjvs, close_after_job=True).publish(make_job())

    assert ("close_shop", "shop-123") in kjvs.calls
