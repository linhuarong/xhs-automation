import json

from app.services.yingdao_desktop_smoke_service import YingdaoDesktopSmokeService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import (
    XHS_YINGDAO_SMOKE_BROWSER_OPEN_FORBIDDEN,
    XHS_YINGDAO_SMOKE_EVIDENCE_INVALID,
    XHS_YINGDAO_SMOKE_XHS_OPEN_FORBIDDEN,
)


def _service(tmp_path):
    handoff = YingdaoLocalHandoffService(queue_root=tmp_path / "queue", worker_root=tmp_path)
    return YingdaoDesktopSmokeService(handoff_service=handoff, worker_root=tmp_path)


def test_prepare_search_smoke_generates_active_job_and_receipt_path(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)

    assert result.status == "waiting_desktop_rpa"
    assert result.expected_receipt_path.endswith("yingdao_smoke_receipt.json")
    assert (tmp_path / "queue" / "search" / "_active_job.json").exists()
    assert (tmp_path / "queue" / "smoke" / "search" / "search-smoke-001" / "active_job_snapshot.json").exists()


def test_prepare_publish_smoke_generates_active_job_and_receipt_path(tmp_path) -> None:
    service = _service(tmp_path)

    result = service.prepare_publish_smoke(
        "publish-smoke-001",
        "xhs_dev_01",
        "测试标题",
        "测试正文",
        ["眼影"],
        [".local_assets/publish-smoke-001/01.png"],
    )

    assert result.status == "waiting_desktop_rpa"
    assert result.expected_receipt_path.endswith("yingdao_smoke_receipt.json")
    assert (tmp_path / "queue" / "publish" / "_active_publish_job.json").exists()


def test_verify_missing_receipt_returns_waiting(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)

    result = service.verify_smoke("search", "search-smoke-001")

    assert result.status == "waiting_desktop_rpa"
    assert result.summary.receipt_exists is False


def test_verify_missing_evidence_returns_waiting(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_receipt_for_local_test("search", "search-smoke-001")

    result = service.verify_smoke("search", "search-smoke-001")

    assert result.status == "waiting_desktop_rpa"
    assert result.summary.receipt_valid is True
    assert result.summary.evidence_exists is False


def test_mock_write_search_writes_receipt_and_evidence_then_verifies(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)

    receipt_path = service.write_mock_receipt_for_local_test("search", "search-smoke-001")
    evidence_path = service.write_mock_evidence_for_local_test("search", "search-smoke-001", "success")
    result = service.verify_smoke("search", "search-smoke-001")

    assert receipt_path.endswith("yingdao_smoke_receipt.json")
    assert evidence_path.endswith("search_evidence.json")
    assert result.status == "verified"
    assert result.summary.receipt_valid is True
    assert result.summary.evidence_valid is True
    assert result.summary.real_action_executed is False


def test_mock_write_publish_writes_receipt_and_evidence_then_verifies(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_publish_smoke("publish-smoke-001", "xhs_dev_01", "测试标题", "测试正文", [], [])

    receipt_path = service.write_mock_receipt_for_local_test("publish", "publish-smoke-001")
    evidence_path = service.write_mock_evidence_for_local_test("publish", "publish-smoke-001", "waiting_manual_review")
    result = service.verify_smoke("publish", "publish-smoke-001")

    assert receipt_path.endswith("yingdao_smoke_receipt.json")
    assert evidence_path.endswith("publish_evidence.json")
    assert result.status == "verified"
    assert result.summary.receipt_valid is True
    assert result.summary.evidence_valid is True


def test_receipt_opened_browser_true_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_receipt_for_local_test("search", "search-smoke-001")
    paths = service.get_smoke_paths("search", "search-smoke-001")
    receipt_path = paths["receipt_path"]
    receipt = json.loads(open(receipt_path, encoding="utf-8").read())
    receipt["rpa_runtime"]["opened_browser"] = True
    with open(receipt_path, "w", encoding="utf-8") as file:
        json.dump(receipt, file)

    result = service.verify_smoke("search", "search-smoke-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_SMOKE_BROWSER_OPEN_FORBIDDEN


def test_receipt_opened_xhs_true_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_receipt_for_local_test("search", "search-smoke-001")
    paths = service.get_smoke_paths("search", "search-smoke-001")
    receipt = json.loads(open(paths["receipt_path"], encoding="utf-8").read())
    receipt["rpa_runtime"]["opened_xhs"] = True
    with open(paths["receipt_path"], "w", encoding="utf-8") as file:
        json.dump(receipt, file)

    result = service.verify_smoke("search", "search-smoke-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_SMOKE_XHS_OPEN_FORBIDDEN


def test_search_evidence_real_search_true_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_search_smoke("search-smoke-001", "xhs_dev_01", "眼影", 20)
    service.write_mock_receipt_for_local_test("search", "search-smoke-001")
    service.write_mock_evidence_for_local_test("search", "search-smoke-001", "success")
    paths = service.get_smoke_paths("search", "search-smoke-001")
    evidence = json.loads(open(paths["evidence_path"], encoding="utf-8").read())
    evidence["smoke_test"]["real_search_executed"] = True
    with open(paths["evidence_path"], "w", encoding="utf-8") as file:
        json.dump(evidence, file)

    result = service.verify_smoke("search", "search-smoke-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_SMOKE_EVIDENCE_INVALID


def test_publish_evidence_real_publish_or_click_true_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_publish_smoke("publish-smoke-001", "xhs_dev_01", "测试标题", "测试正文", [], [])
    service.write_mock_receipt_for_local_test("publish", "publish-smoke-001")
    service.write_mock_evidence_for_local_test("publish", "publish-smoke-001", "waiting_manual_review")
    paths = service.get_smoke_paths("publish", "publish-smoke-001")
    evidence = json.loads(open(paths["evidence_path"], encoding="utf-8").read())
    evidence["smoke_test"]["real_publish_executed"] = True
    with open(paths["evidence_path"], "w", encoding="utf-8") as file:
        json.dump(evidence, file)

    result = service.verify_smoke("publish", "publish-smoke-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_SMOKE_EVIDENCE_INVALID


def test_publish_evidence_clicked_final_publish_true_fails(tmp_path) -> None:
    service = _service(tmp_path)
    service.prepare_publish_smoke("publish-smoke-001", "xhs_dev_01", "测试标题", "测试正文", [], [])
    service.write_mock_receipt_for_local_test("publish", "publish-smoke-001")
    service.write_mock_evidence_for_local_test("publish", "publish-smoke-001", "waiting_manual_review")
    paths = service.get_smoke_paths("publish", "publish-smoke-001")
    evidence = json.loads(open(paths["evidence_path"], encoding="utf-8").read())
    evidence["smoke_test"]["clicked_final_publish"] = True
    with open(paths["evidence_path"], "w", encoding="utf-8") as file:
        json.dump(evidence, file)

    result = service.verify_smoke("publish", "publish-smoke-001")

    assert result.status == "failed"
    assert result.error_code == XHS_YINGDAO_SMOKE_EVIDENCE_INVALID
