import json

from app.services.external_readiness_service import ExternalReadinessService


def _dependency(result, name):
    return next(item for item in result.dependencies if item.name == name)


def test_default_readiness_safe_mode_without_env(tmp_path) -> None:
    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()

    assert result.status == "success"
    assert result.safe_mode is True
    assert result.environment == "local"
    assert result.summary.total == 20


def test_missing_kjvs_profile_map_is_missing_config(tmp_path) -> None:
    result = ExternalReadinessService(
        env={"KJVS_API_BASE_URL": "http://127.0.0.1:49709"},
        worker_root=tmp_path,
    ).check_all()

    kuaijingvs = _dependency(result, "kuaijingvs")
    assert kuaijingvs.status == "missing_config"
    assert kuaijingvs.checks["profile_map_path_configured"] is False


def test_valid_profile_map_makes_kuaijingvs_ready(tmp_path) -> None:
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        json.dumps(
            {
                "xhs_dev_01": {
                    "shop_id": "shop-1",
                    "shop_name": "小红书测试账号01",
                    "provider_type": "kuaijingvs_yingdao_rpa",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = ExternalReadinessService(
        env={
            "KJVS_API_BASE_URL": "http://127.0.0.1:49709",
            "KJVS_PROFILE_MAP_PATH": ".config/kuaijingvs_profiles.json",
        },
        worker_root=tmp_path,
    ).check_all()

    kuaijingvs = _dependency(result, "kuaijingvs")
    assert kuaijingvs.status == "ready"
    assert kuaijingvs.mode == "dry_run"
    assert kuaijingvs.checks["profile_map_valid"] is True
    assert kuaijingvs.checks["profile_count"] == 1
    assert kuaijingvs.checks["live_readonly_enabled"] is False


def test_invalid_profile_map_json_is_failed(tmp_path) -> None:
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text("{bad", encoding="utf-8")

    result = ExternalReadinessService(
        env={
            "KJVS_API_BASE_URL": "http://127.0.0.1:49709",
            "KJVS_PROFILE_MAP_PATH": ".config/kuaijingvs_profiles.json",
        },
        worker_root=tmp_path,
    ).check_all()

    kuaijingvs = _dependency(result, "kuaijingvs")
    assert kuaijingvs.status == "failed"
    assert "JSON invalid" in kuaijingvs.message


def test_n8n_and_openclaw_contracts_are_mock_ready(tmp_path) -> None:
    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()

    assert _dependency(result, "n8n").status == "mock_ready"
    assert _dependency(result, "n8n").checks["webhook_search_route"] is True
    assert _dependency(result, "openclaw").status == "mock_ready"
    assert _dependency(result, "openclaw").checks["job_status_route"] is True


def test_yingdao_local_handoff_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for script_name in [
        "xhs_yingdao_prepare_search_handoff.ps1",
        "xhs_yingdao_prepare_publish_handoff.ps1",
        "xhs_yingdao_check_active_job.ps1",
        "xhs_yingdao_mock_evidence.ps1",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    handoff = _dependency(result, "yingdao_local_handoff")

    assert handoff.mode == "local_file_contract"
    assert handoff.checks["search_active_job_path_configured"] is True
    assert handoff.checks["publish_active_job_path_configured"] is True
    assert handoff.checks["safe_mode"] is True


def test_yingdao_desktop_smoke_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for script_name in [
        "xhs_yingdao_prepare_search_handoff.ps1",
        "xhs_yingdao_prepare_publish_handoff.ps1",
        "xhs_yingdao_check_active_job.ps1",
        "xhs_yingdao_mock_evidence.ps1",
        "xhs_yingdao_desktop_smoke_prepare.ps1",
        "xhs_yingdao_desktop_smoke_verify.ps1",
        "xhs_yingdao_desktop_smoke_mock_write.ps1",
        "xhs_yingdao_desktop_smoke_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    smoke = _dependency(result, "yingdao_desktop_smoke")

    assert smoke.mode == "manual_local_file_smoke"
    assert smoke.checks["mock_write_available"] is True
    assert smoke.checks["real_yingdao_api_disabled"] is True
    assert smoke.checks["browser_open_disabled"] is True


def test_yingdao_form_fill_simulator_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_yingdao_form_sim_prepare.ps1",
        "xhs_yingdao_form_sim_verify.ps1",
        "xhs_yingdao_form_sim_mock_write.ps1",
        "xhs_yingdao_form_sim_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    simulator = _dependency(result, "yingdao_form_fill_simulator")

    assert simulator.mode == "browserless_local_json_simulator"
    assert simulator.checks["mock_write_available"] is True
    assert simulator.checks["browser_open_disabled"] is True
    assert simulator.checks["xhs_open_disabled"] is True
    assert simulator.checks["real_actions_disabled"] is True


def test_yingdao_local_html_sandbox_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_yingdao_html_sandbox_prepare.ps1",
        "xhs_yingdao_html_sandbox_open.ps1",
        "xhs_yingdao_html_sandbox_verify.ps1",
        "xhs_yingdao_html_sandbox_mock_write.ps1",
        "xhs_yingdao_html_sandbox_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    sandbox = _dependency(result, "yingdao_local_html_sandbox")

    assert sandbox.mode == "local_static_html_sandbox"
    assert sandbox.checks["mock_write_available"] is True
    assert sandbox.checks["external_url_forbidden"] is True
    assert sandbox.checks["xhs_url_forbidden"] is True
    assert sandbox.checks["real_yingdao_api_disabled"] is True


def test_yingdao_selector_mapping_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_yingdao_selector_mapping_prepare.ps1",
        "xhs_yingdao_selector_mapping_open_report.ps1",
        "xhs_yingdao_selector_mapping_verify.ps1",
        "xhs_yingdao_selector_mapping_mock_confirm.ps1",
        "xhs_yingdao_selector_mapping_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    mapping = _dependency(result, "yingdao_selector_mapping")

    assert mapping.mode == "local_html_selector_mapping_report"
    assert mapping.checks["mock_confirm_available"] is True
    assert mapping.checks["external_url_forbidden"] is True
    assert mapping.checks["xhs_url_forbidden"] is True
    assert mapping.checks["real_publish_forbidden"] is True


def test_yingdao_actual_form_fill_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_yingdao_actual_form_fill_prepare.ps1",
        "xhs_yingdao_actual_form_fill_open.ps1",
        "xhs_yingdao_actual_form_fill_verify.ps1",
        "xhs_yingdao_actual_form_fill_mock_write.ps1",
        "xhs_yingdao_actual_form_fill_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    actual = _dependency(result, "yingdao_actual_form_fill")

    assert actual.mode == "local_html_actual_form_fill_smoke"
    assert actual.checks["mock_write_available"] is True
    assert actual.checks["open_local_html_available"] is True
    assert actual.checks["external_url_forbidden"] is True
    assert actual.checks["xhs_url_forbidden"] is True
    assert actual.checks["real_publish_forbidden"] is True


def test_xhs_account_binding_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_account_binding_prepare.ps1",
        "xhs_account_binding_verify.ps1",
        "xhs_account_binding_mock_confirm.ps1",
        "xhs_account_binding_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        json.dumps(
            {
                "xhs_dev_01": {
                    "shop_id": "123456",
                    "shop_name": "灏忕孩涔︽祴璇曡处鍙?1",
                    "provider_type": "kuaijingvs_yingdao_rpa",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    binding = _dependency(result, "xhs_account_binding")

    assert binding.mode == "kuaijingvs_profile_to_local_yingdao_binding"
    assert binding.checks["profile_map_exists"] is True
    assert binding.checks["profile_map_valid"] is True
    assert binding.checks["account_binding_scripts_available"] is True
    assert binding.checks["mock_confirm_available"] is True
    assert binding.checks["kuaijingvs_open_shop_forbidden"] is True
    assert binding.checks["xhs_url_forbidden"] is True
    assert binding.checks["real_publish_forbidden"] is True


def test_kuaijingvs_discovery_hardening_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "xhs_kjvs_discovery_harden.ps1").write_text("", encoding="utf-8")
    source_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    summary_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery_summary.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('{"shops":[]}', encoding="utf-8")
    hardened_path.write_text(
        json.dumps(
            {
                "status": "success",
                "sanitization": {"sensitive_value_scan_passed": True},
                "forbidden": {"opened_shop": False},
                "errors": [],
                "evidence_hash": "sha256:test",
            }
        ),
        encoding="utf-8",
    )
    summary_path.write_text('{"status":"success"}', encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    hardening = _dependency(result, "kuaijingvs_discovery_hardening")

    assert hardening.mode == "local_evidence_hardening"
    assert hardening.checks["source_discovery_exists"] is True
    assert hardening.checks["hardened_discovery_exists"] is True
    assert hardening.checks["evidence_hash_available"] is True
    assert hardening.checks["open_shop_forbidden"] is True


def test_xhs_account_binding_strict_mode_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_account_binding_strict_check.ps1",
        "xhs_account_binding_strict_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")
    profile_path = tmp_path / ".config" / "kuaijingvs_profiles.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        json.dumps(
            {
                "xhs_dev_01": {
                    "shop_id": "123456",
                    "shop_name": "灏忕孩涔︽祴璇曡处鍙?1",
                    "provider_type": "kuaijingvs_yingdao_rpa",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    hardened_path.parent.mkdir(parents=True)
    hardened_path.write_text(
        json.dumps(
            {
                "status": "success",
                "sanitization": {"sensitive_value_scan_passed": True},
                "forbidden": {"opened_shop": False},
                "errors": [],
                "evidence_hash": "sha256:test",
            }
        ),
        encoding="utf-8",
    )

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    strict = _dependency(result, "xhs_account_binding_strict_mode")

    assert strict.mode == "local_strict_binding_check"
    assert strict.checks["profile_map_exists"] is True
    assert strict.checks["hardened_discovery_safe"] is True
    assert strict.checks["strict_scripts_available"] is True
    assert strict.checks["open_shop_forbidden"] is True


def test_local_contract_replay_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_contract_replay_n8n_search.ps1",
        "xhs_contract_replay_n8n_publish.ps1",
        "xhs_contract_replay_openclaw_status.ps1",
        "xhs_contract_replay_all.ps1",
        "xhs_contract_replay_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")
    hardened_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "hardened_discovery.json"
    hardened_path.parent.mkdir(parents=True)
    hardened_path.write_text(
        json.dumps(
            {
                "status": "success",
                "sanitization": {"sensitive_value_scan_passed": True},
                "forbidden": {"opened_shop": False},
                "errors": [],
                "evidence_hash": "sha256:test",
            }
        ),
        encoding="utf-8",
    )

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    replay = _dependency(result, "local_contract_replay")

    assert replay.mode == "local_n8n_openclaw_replay"
    assert replay.checks["n8n_mock_search_route_available"] is True
    assert replay.checks["n8n_mock_publish_route_available"] is True
    assert replay.checks["openclaw_mock_job_status_route_available"] is True
    assert replay.checks["replay_scripts_available"] is True
    assert replay.checks["hardened_discovery_available"] is True
    assert replay.checks["external_n8n_call_forbidden"] is True
    assert replay.checks["external_openclaw_call_forbidden"] is True


def test_local_persistence_replay_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_persistence_replay_feishu_search.ps1",
        "xhs_persistence_replay_feishu_publish.ps1",
        "xhs_persistence_replay_postgres_search.ps1",
        "xhs_persistence_replay_postgres_publish.ps1",
        "xhs_persistence_replay_minio_search.ps1",
        "xhs_persistence_replay_minio_publish.ps1",
        "xhs_persistence_replay_all.ps1",
        "xhs_persistence_replay_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    persistence = _dependency(result, "local_persistence_replay")

    assert persistence.mode == "local_feishu_postgres_minio_mock_persistence"
    assert persistence.checks["persistence_replay_enabled"] is True
    assert persistence.checks["feishu_mock_enabled"] is True
    assert persistence.checks["postgres_mock_enabled"] is True
    assert persistence.checks["minio_mock_enabled"] is True
    assert persistence.checks["real_feishu_write_forbidden"] is True
    assert persistence.checks["real_postgres_write_forbidden"] is True
    assert persistence.checks["real_minio_upload_forbidden"] is True
    assert persistence.checks["persistence_scripts_available"] is True


def test_local_e2e_replay_dependency_is_reported(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    for script_name in [
        "xhs_e2e_replay_search.ps1",
        "xhs_e2e_replay_publish.ps1",
        "xhs_e2e_replay_all.ps1",
        "xhs_e2e_replay_runbook.txt",
    ]:
        (scripts / script_name).write_text("", encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    e2e = _dependency(result, "local_e2e_replay")

    assert e2e.mode == "local_full_e2e_replay_orchestrator"
    assert e2e.checks["e2e_replay_enabled"] is True
    assert e2e.checks["contract_replay_available"] is True
    assert e2e.checks["persistence_replay_available"] is True
    assert e2e.checks["strict_binding_required"] is True
    assert e2e.checks["hardened_discovery_required"] is True
    assert e2e.checks["real_external_calls_forbidden"] is True
    assert e2e.checks["scripts_available"] is True


def test_readiness_reads_existing_discovery_evidence_without_live_call(tmp_path) -> None:
    evidence_path = tmp_path / ".local_evidence" / "kuaijingvs_discovery" / "discovery.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text('{"status":"success"}', encoding="utf-8")

    result = ExternalReadinessService(env={}, worker_root=tmp_path).check_all()
    kuaijingvs = _dependency(result, "kuaijingvs")

    assert kuaijingvs.checks["discovery_api_available"] is True
    assert kuaijingvs.checks["last_discovery_evidence_path"] == str(evidence_path)


def test_live_write_flag_disables_safe_mode(tmp_path) -> None:
    result = ExternalReadinessService(
        env={"XHS_ALLOW_LIVE_WRITE_ACTIONS": "true"},
        worker_root=tmp_path,
    ).check_all()

    assert result.safe_mode is False
