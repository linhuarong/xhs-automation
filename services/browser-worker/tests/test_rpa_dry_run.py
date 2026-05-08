import json
from pathlib import Path

from app.schemas.search_job import SearchJob
from app.services.kuaijingvs_service import KuaJingVSService
from app.services.rpa_dry_run import RpaDryRunService
from app.services.yingdao_service import YingdaoService
from app.utils.errors import (
    KJVS_PROFILE_NOT_FOUND,
    RPA_DRY_RUN_CONFIG_ERROR,
    RPA_DRY_RUN_PROFILE_MAP_NOT_FOUND,
    YINGDAO_CONFIG_ERROR,
)


class NoopHttpClient:
    """HTTP client that fails if a test accidentally reaches the network layer."""

    def get_json(self, url, headers=None):
        """Prevent real GET calls in dry-run tests."""
        raise AssertionError(f"unexpected GET call: {url}")

    def post_json(self, url, payload, headers=None):
        """Prevent real POST calls in dry-run tests."""
        raise AssertionError(f"unexpected POST call: {url}")


def write_profile_map(path, content=None):
    data = content or {
        "xhs_dev_01": {
            "shop_id": "123456",
            "shop_name": "小红书测试账号01",
            "provider_type": "kuaijingvs_yingdao_rpa",
        }
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def make_job(provider_type="kuaijingvs_yingdao_rpa"):
    return SearchJob(
        job_id="dry-run-1",
        account_id="xhs_dev_01",
        keyword="眼影",
        provider_type=provider_type,
    )


def make_service(profile_map_path, evidence_root, robot_uuid="robot-uuid"):
    kuaijingvs_service = KuaJingVSService(
        profile_map_path=str(profile_map_path),
        http_client=NoopHttpClient(),
    )
    yingdao_service = YingdaoService(
        account_name="yingdao-account",
        robot_uuid=robot_uuid,
        http_client=NoopHttpClient(),
    )
    return RpaDryRunService(
        kuaijingvs_service=kuaijingvs_service,
        yingdao_service=yingdao_service,
        evidence_root=evidence_root,
    )


def test_rpa_dry_run_success(tmp_path):
    profile_map_path = tmp_path / "kuaijingvs_profiles.json"
    evidence_root = tmp_path / ".local_evidence"
    write_profile_map(profile_map_path)

    report = make_service(profile_map_path, evidence_root).check_search_job(make_job())

    assert report["status"] == "success"
    assert report["resolved"]["shop_id"] == "123456"
    assert Path(report["resolved"]["expected_evidence_json_path"]).parts[-2:] == (
        "dry-run-1",
        "search_evidence.json",
    )
    assert Path(report["resolved"]["expected_screenshot_path"]).parts[-2:] == (
        "dry-run-1",
        "xhs_search_smoke.png",
    )


def test_rpa_dry_run_profile_map_missing(tmp_path):
    missing_path = tmp_path / "missing_profiles.json"
    report = make_service(missing_path, tmp_path / ".local_evidence").check_search_job(make_job())

    assert report["status"] == "failed"
    assert report["error_code"] == RPA_DRY_RUN_PROFILE_MAP_NOT_FOUND


def test_rpa_dry_run_account_not_found(tmp_path):
    profile_map_path = tmp_path / "kuaijingvs_profiles.json"
    write_profile_map(profile_map_path, {"other_account": {"shop_id": "999"}})

    report = make_service(profile_map_path, tmp_path / ".local_evidence").check_search_job(
        make_job()
    )

    assert report["status"] == "failed"
    assert report["error_code"] == KJVS_PROFILE_NOT_FOUND


def test_rpa_dry_run_missing_yingdao_robot_uuid(tmp_path):
    profile_map_path = tmp_path / "kuaijingvs_profiles.json"
    write_profile_map(profile_map_path)

    report = make_service(
        profile_map_path,
        tmp_path / ".local_evidence",
        robot_uuid="",
    ).check_search_job(make_job())

    assert report["status"] == "failed"
    assert report["error_code"] == YINGDAO_CONFIG_ERROR


def test_rpa_dry_run_creates_evidence_dir_without_files(tmp_path):
    profile_map_path = tmp_path / "kuaijingvs_profiles.json"
    evidence_root = tmp_path / ".local_evidence"
    write_profile_map(profile_map_path)

    report = make_service(profile_map_path, evidence_root).check_search_job(make_job())
    evidence_dir = evidence_root / "dry-run-1"

    assert report["status"] == "success"
    assert evidence_dir.exists()
    assert not (evidence_dir / "search_evidence.json").exists()
    assert not (evidence_dir / "xhs_search_smoke.png").exists()


def test_rpa_dry_run_provider_type_unsupported(tmp_path):
    profile_map_path = tmp_path / "kuaijingvs_profiles.json"
    write_profile_map(profile_map_path)

    report = make_service(profile_map_path, tmp_path / ".local_evidence").check_search_job(
        make_job(provider_type="selenium_chrome")
    )

    assert report["status"] == "failed"
    assert report["error_code"] == RPA_DRY_RUN_CONFIG_ERROR
    assert "selenium_chrome" in report["error_message"]
