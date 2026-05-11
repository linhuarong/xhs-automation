from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_kjvs_discovery_script_contract() -> None:
    script = (SCRIPT_ROOT / "xhs_kjvs_discovery.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in script
    assert "/api/workflows/xhs/kuaijingvs/discovery" in script
    assert "XHS_ALLOW_LIVE_READONLY_CHECKS=true" in script
    assert "shop_count" in script
    assert "evidence_json_path" in script


def test_validate_profile_map_script_allows_expected_provider_types() -> None:
    script = (SCRIPT_ROOT / "xhs_validate_profile_map.ps1").read_text(encoding="utf-8")

    assert "kuaijingvs_yingdao_rpa" in script
    assert "yingdao_rpa" in script
    assert "manual" in script
    assert "selenium_chrome_debug" in script
