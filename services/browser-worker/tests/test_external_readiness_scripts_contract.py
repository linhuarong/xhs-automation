from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_external_readiness_script_contract() -> None:
    script = (SCRIPT_ROOT / "xhs_external_readiness.ps1").read_text(encoding="utf-8")

    assert "BaseUrl" in script
    assert "/api/workflows/xhs/external-readiness" in script
    assert "summary" in script


def test_validate_profile_map_script_contract() -> None:
    script = (SCRIPT_ROOT / "xhs_validate_profile_map.ps1").read_text(encoding="utf-8")

    assert "ProfileMapPath" in script
    assert "kuaijingvs_profiles.json" in script
    assert "shop_id" in script
    assert "shop_name" in script
    assert "provider_type" in script
    assert "kuaijingvs_yingdao_rpa" in script
