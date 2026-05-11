from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def test_contract_replay_scripts_and_runbook_exist() -> None:
    for name in [
        "xhs_contract_replay_n8n_search.ps1",
        "xhs_contract_replay_n8n_publish.ps1",
        "xhs_contract_replay_openclaw_status.ps1",
        "xhs_contract_replay_all.ps1",
        "xhs_contract_replay_runbook.txt",
    ]:
        assert (SCRIPTS_DIR / name).exists()


def test_contract_replay_scripts_call_local_workflow_apis_only() -> None:
    search = (SCRIPTS_DIR / "xhs_contract_replay_n8n_search.ps1").read_text(encoding="utf-8")
    publish = (SCRIPTS_DIR / "xhs_contract_replay_n8n_publish.ps1").read_text(encoding="utf-8")
    openclaw = (SCRIPTS_DIR / "xhs_contract_replay_openclaw_status.ps1").read_text(encoding="utf-8")
    replay_all = (SCRIPTS_DIR / "xhs_contract_replay_all.ps1").read_text(encoding="utf-8")
    combined = "\n".join([search, publish, openclaw, replay_all]).lower()

    assert "/api/workflows/xhs/contract-replay/n8n/search" in search
    assert "/api/workflows/xhs/contract-replay/n8n/publish" in publish
    assert "/api/workflows/xhs/contract-replay/openclaw/job-status" in openclaw
    assert "/api/workflows/xhs/contract-replay/all/search" in replay_all
    assert "/api/workflows/xhs/contract-replay/all/publish" in replay_all
    assert "n8n_base_url" not in combined
    assert "openclaw_base_url" not in combined
    assert "http://n8n" not in combined
    assert "https://n8n" not in combined
    assert "openclaw.example" not in combined


def test_contract_replay_runbook_states_safety_boundaries() -> None:
    text = (SCRIPTS_DIR / "xhs_contract_replay_runbook.txt").read_text(encoding="utf-8")

    assert "不调用真实 n8n" in text
    assert "不调用真实 OpenClaw" in text
    assert "不要 open shop" in text
    assert "不要打开小红书" in text
    assert "不要点击真实发布" in text
