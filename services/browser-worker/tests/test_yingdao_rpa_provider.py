import json

from app.providers.yingdao_rpa import EVIDENCE_NOT_FOUND, YingdaoRpaProvider
from app.schemas import STATUS_FAILED, STATUS_SUCCESS, STATUS_WAITING_HUMAN_VERIFICATION, SearchJob


class FakeYingdaoService:
    def __init__(self, evidence_json_path: str | None = None) -> None:
        self.account_name = "account"
        self.robot_uuid = "robot"
        self.evidence_json_path = evidence_json_path
        self.started_params: list[dict] | None = None

    def start_job(self, account_name: str, robot_uuid: str, params: list[dict]) -> dict:
        self.started_params = params
        return {"job_uuid": "yingdao-job-1"}

    def wait_job_done(self, job_uuid: str) -> dict:
        return {"status": "success", "outputs": {"evidence_json_path": self.evidence_json_path}}

    def extract_outputs(self, job_result: dict) -> dict:
        return job_result["outputs"]


def _search_job() -> SearchJob:
    return SearchJob(
        job_id="yingdao-test-1",
        account_id="xhs_dev_01",
        provider_type="yingdao_rpa",
        keyword="\u773c\u5f71",
        limit=5,
    )


def _write_evidence(path, status: str = STATUS_SUCCESS) -> None:
    path.write_text(
        json.dumps(
            {
                "job_id": "yingdao-test-1",
                "status": status,
                "message": "search completed" if status == STATUS_SUCCESS else None,
                "keyword": "\u773c\u5f71",
                "screenshot_path": ".local_evidence/yingdao-test-1/xhs_search_smoke.png",
                "items": [{"rank": 1, "title": "\u773c\u5f71\u6807\u9898"}],
                "normalized_records": [
                    {
                        "rank": 1,
                        "keyword": "\u773c\u5f71",
                        "title": "\u773c\u5f71\u6807\u9898",
                    }
                ],
                "error_code": "WAITING_HUMAN_VERIFICATION"
                if status == STATUS_WAITING_HUMAN_VERIFICATION
                else None,
                "error_message": "manual required"
                if status == STATUS_WAITING_HUMAN_VERIFICATION
                else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_yingdao_rpa_provider_reads_evidence_success(tmp_path) -> None:
    evidence_path = tmp_path / "search_evidence.json"
    _write_evidence(evidence_path)
    service = FakeYingdaoService(evidence_json_path=str(evidence_path))
    provider = YingdaoRpaProvider(service=service, evidence_root=tmp_path)

    result = provider.search(_search_job())

    assert result.status == STATUS_SUCCESS
    assert result.message == "search completed"
    assert result.screenshot_url == ".local_evidence/yingdao-test-1/xhs_search_smoke.png"
    assert result.evidence_json_path == str(evidence_path)
    assert result.items == [{"rank": 1, "title": "\u773c\u5f71\u6807\u9898"}]
    assert result.normalized_records == [
        {"rank": 1, "keyword": "\u773c\u5f71", "title": "\u773c\u5f71\u6807\u9898"}
    ]
    assert service.started_params is not None
    assert {"name": "keyword", "value": "\u773c\u5f71"} in service.started_params


def test_yingdao_rpa_provider_missing_evidence_returns_failed(tmp_path) -> None:
    evidence_path = tmp_path / "missing" / "search_evidence.json"
    provider = YingdaoRpaProvider(
        service=FakeYingdaoService(evidence_json_path=str(evidence_path)),
        evidence_root=tmp_path,
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_FAILED
    assert result.error_code == EVIDENCE_NOT_FOUND
    assert result.evidence_json_path == str(evidence_path)


def test_yingdao_rpa_provider_waiting_human_status(tmp_path) -> None:
    evidence_path = tmp_path / "search_evidence.json"
    _write_evidence(evidence_path, status=STATUS_WAITING_HUMAN_VERIFICATION)
    provider = YingdaoRpaProvider(
        service=FakeYingdaoService(evidence_json_path=str(evidence_path)),
        evidence_root=tmp_path,
    )

    result = provider.search(_search_job())

    assert result.status == STATUS_WAITING_HUMAN_VERIFICATION
    assert result.error_code == "WAITING_HUMAN_VERIFICATION"
    assert result.error_message == "manual required"
