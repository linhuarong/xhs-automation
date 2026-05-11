import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    XhsE2EReplayRequest,
    XhsE2EReplayResult,
    XhsE2EReplayStepResult,
    XhsE2EReplaySummary,
)
from app.services.external_readiness_service import ExternalReadinessService
from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.local_persistence_replay_service import LocalPersistenceReplayService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_E2E_REPLAY_ARTIFACT_MANIFEST_INVALID,
    XHS_E2E_REPLAY_CONTRACT_REPLAY_FAILED,
    XHS_E2E_REPLAY_ERROR,
    XHS_E2E_REPLAY_HARDENED_DISCOVERY_FAILED,
    XHS_E2E_REPLAY_PERSISTENCE_REPLAY_FAILED,
    XHS_E2E_REPLAY_READINESS_FAILED,
    XHS_E2E_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
    XHS_E2E_REPLAY_STRICT_BINDING_FAILED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "set-cookie",
    "secret",
    "password",
    "passwd",
    "authorization",
    "auth",
    "api_key",
    "app_secret",
    "session",
    "credential",
    "private_key",
    "header",
    "headers",
}
SENSITIVE_VALUE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"Bearer\s+",
        r"Cookie:",
        r"sessionid=",
        r"access_token=",
        r"refresh_token=",
        r"password=",
        r"secret=",
        r"Authorization",
    )
]


class LocalE2EReplayService:
    """Orchestrate local readiness, strict binding, contract replay, and persistence replay."""

    def __init__(
        self,
        readiness_service: ExternalReadinessService | None = None,
        account_binding_service: XhsAccountBindingService | None = None,
        contract_replay_service: LocalContractReplayService | None = None,
        persistence_replay_service: LocalPersistenceReplayService | None = None,
        e2e_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.readiness_service = readiness_service or ExternalReadinessService(worker_root=self.worker_root)
        self.account_binding_service = account_binding_service or XhsAccountBindingService(worker_root=self.worker_root)
        self.contract_replay_service = contract_replay_service or LocalContractReplayService(
            account_binding_service=self.account_binding_service,
            worker_root=self.worker_root,
        )
        self.persistence_replay_service = persistence_replay_service or LocalPersistenceReplayService(
            contract_replay_service=self.contract_replay_service,
            account_binding_service=self.account_binding_service,
            worker_root=self.worker_root,
        )
        self.e2e_root = self._resolve_worker_path(e2e_root or os.getenv("XHS_LOCAL_E2E_REPLAY_ROOT", ".local_rpa_queue/e2e"))

    def replay_search(
        self,
        run_id: str,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> XhsE2EReplayResult:
        """Run local search E2E replay."""
        request = XhsE2EReplayRequest(
            run_id=run_id,
            job_type="search",
            account_id=account_id,
            search_job_id=job_id,
            keyword=keyword,
            limit=limit,
        )
        return self._run(request)

    def replay_publish(
        self,
        run_id: str,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> XhsE2EReplayResult:
        """Run local publish E2E replay."""
        request = XhsE2EReplayRequest(
            run_id=run_id,
            job_type="publish",
            account_id=account_id,
            publish_job_id=job_id,
            title=title,
            body=body,
            tags=tags,
            image_paths=image_paths,
            publish_mode=publish_mode,
        )
        return self._run(request)

    def replay_all(
        self,
        run_id: str,
        account_id: str,
        keyword: str,
        limit: int,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
        search_job_id: str | None = None,
        publish_job_id: str | None = None,
    ) -> XhsE2EReplayResult:
        """Run local search and publish E2E replay in one run."""
        request = XhsE2EReplayRequest(
            run_id=run_id,
            job_type="all",
            account_id=account_id,
            search_job_id=search_job_id or f"{run_id}-search",
            publish_job_id=publish_job_id or f"{run_id}-publish",
            keyword=keyword,
            limit=limit,
            title=title,
            body=body,
            tags=tags,
            image_paths=image_paths,
            publish_mode=publish_mode,
        )
        return self._run(request)

    def build_e2e_input(self, request: XhsE2EReplayRequest) -> dict[str, Any]:
        """Build local E2E input JSON."""
        payload = self._model_to_dict(request)
        payload.update(
            {
                "schema_version": "1.0",
                "replay_type": "local_full_e2e_replay",
                "created_at": self._utc_now(),
                "safe_mode": True,
                "forbidden": self._forbidden_actions(),
            }
        )
        scan = self.scan_sensitive_artifacts(payload)
        if not scan["passed"]:
            raise WorkerError(XHS_E2E_REPLAY_SENSITIVE_PAYLOAD_DETECTED, f"E2E input contains sensitive content: {scan['matches']}")
        return payload

    def run_readiness_check(self) -> dict[str, Any]:
        """Run safe readiness check without external actions."""
        result = self.readiness_service.check_all()
        status = getattr(result, "status", "failed")
        if status != "success":
            raise WorkerError(XHS_E2E_REPLAY_READINESS_FAILED, f"external readiness failed: {status}")
        return self._model_to_dict(result)

    def run_or_load_strict_binding(self, job_type: str, request: XhsE2EReplayRequest) -> dict[str, Any]:
        """Run strict account binding for one job."""
        if job_type == "search":
            result = self.account_binding_service.prepare_search_strict_binding_check(
                request.search_job_id or request.run_id,
                request.account_id,
                request.keyword or "",
                request.limit,
            )
        else:
            result = self.account_binding_service.prepare_publish_strict_binding_check(
                request.publish_job_id or request.run_id,
                request.account_id,
                request.title or "",
                request.body or "",
                list(request.tags or []),
                list(request.image_paths or []),
                request.publish_mode,
            )
        payload = self._model_to_dict(result)
        if payload.get("status") != "success" or payload.get("binding_status") != "strict_matched":
            raise WorkerError(XHS_E2E_REPLAY_STRICT_BINDING_FAILED, f"strict binding failed: {payload.get('binding_status')}")
        return payload

    def run_or_load_hardened_discovery(self) -> dict[str, Any]:
        """Load hardened discovery reference through persistence replay guard."""
        try:
            return self.persistence_replay_service.load_hardened_discovery_reference()
        except WorkerError as exc:
            raise WorkerError(XHS_E2E_REPLAY_HARDENED_DISCOVERY_FAILED, exc.error_message) from exc

    def run_contract_replay_search(self, request: XhsE2EReplayRequest) -> dict[str, Any]:
        """Run local search contract replay."""
        result = self.contract_replay_service.replay_all_for_job(
            request.search_job_id or request.run_id,
            "xhs_search",
            request.account_id,
            {"keyword": request.keyword or "", "limit": request.limit},
        )
        payload = self._model_to_dict(result)
        if payload.get("status") != "success":
            raise WorkerError(XHS_E2E_REPLAY_CONTRACT_REPLAY_FAILED, payload.get("error_message") or "search contract replay failed")
        return payload

    def run_contract_replay_publish(self, request: XhsE2EReplayRequest) -> dict[str, Any]:
        """Run local publish contract replay."""
        result = self.contract_replay_service.replay_all_for_job(
            request.publish_job_id or request.run_id,
            "xhs_publish",
            request.account_id,
            {
                "title": request.title or "",
                "body": request.body or "",
                "tags": list(request.tags or []),
                "image_paths": list(request.image_paths or []),
                "publish_mode": request.publish_mode,
            },
        )
        payload = self._model_to_dict(result)
        if payload.get("status") != "success":
            raise WorkerError(XHS_E2E_REPLAY_CONTRACT_REPLAY_FAILED, payload.get("error_message") or "publish contract replay failed")
        return payload

    def run_persistence_replay_search(self, request: XhsE2EReplayRequest) -> dict[str, Any]:
        """Run local search persistence replay."""
        result = self.persistence_replay_service.replay_all_for_job(request.search_job_id or request.run_id, "search", request.account_id)
        payload = self._model_to_dict(result)
        if payload.get("status") != "success":
            raise WorkerError(XHS_E2E_REPLAY_PERSISTENCE_REPLAY_FAILED, payload.get("error_message") or "search persistence replay failed")
        return payload

    def run_persistence_replay_publish(self, request: XhsE2EReplayRequest) -> dict[str, Any]:
        """Run local publish persistence replay."""
        result = self.persistence_replay_service.replay_all_for_job(request.publish_job_id or request.run_id, "publish", request.account_id)
        payload = self._model_to_dict(result)
        if payload.get("status") != "success":
            raise WorkerError(XHS_E2E_REPLAY_PERSISTENCE_REPLAY_FAILED, payload.get("error_message") or "publish persistence replay failed")
        return payload

    def build_artifacts_manifest(self, run_id: str, job_type: str, artifacts: list[str]) -> dict[str, Any]:
        """Build artifacts manifest for generated local files."""
        manifest = {
            "schema_version": "1.0",
            "manifest_type": "local_full_e2e_replay_artifacts",
            "run_id": run_id,
            "job_type": job_type,
            "generated_at": self._utc_now(),
            "artifacts": [{"path": path, "exists": Path(path).exists()} for path in artifacts],
            "forbidden": self._forbidden_actions(),
        }
        scan = self.scan_sensitive_artifacts(manifest)
        if not scan["passed"]:
            raise WorkerError(XHS_E2E_REPLAY_ARTIFACT_MANIFEST_INVALID, f"artifact manifest contains sensitive content: {scan['matches']}")
        return manifest

    def scan_sensitive_artifacts(self, payload: Any) -> dict[str, Any]:
        """Scan dict/list/string values for sensitive keys or values."""
        matches: list[str] = []

        def visit(value: Any, path: str = "$") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    lowered = str(key).strip().lower()
                    if lowered in SENSITIVE_KEYS or any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
                        matches.append(f"{path}.{key}")
                    visit(child, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, f"{path}[{index}]")
            elif isinstance(value, str) and any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
                matches.append(path)

        visit(payload)
        return {"passed": not matches, "matches": matches}

    def write_e2e_input(self, run_id: str, payload: dict[str, Any]) -> str:
        """Write e2e_input.json."""
        return self._write_json(Path(self.get_e2e_paths(run_id)["input_path"]), payload)

    def write_e2e_result(self, run_id: str, payload: dict[str, Any]) -> str:
        """Write e2e_result.json."""
        return self._write_json(Path(self.get_e2e_paths(run_id)["result_path"]), payload)

    def write_e2e_summary(self, run_id: str, payload: dict[str, Any]) -> str:
        """Write e2e_summary.json."""
        return self._write_json(Path(self.get_e2e_paths(run_id)["summary_path"]), payload)

    def write_artifacts_manifest(self, run_id: str, payload: dict[str, Any]) -> str:
        """Write e2e_artifacts_manifest.json."""
        return self._write_json(Path(self.get_e2e_paths(run_id)["artifacts_manifest_path"]), payload)

    def get_e2e_paths(self, run_id: str) -> dict[str, str]:
        """Return local E2E output paths."""
        e2e_dir = self.e2e_root / run_id
        return {
            "e2e_dir": str(e2e_dir),
            "input_path": str(e2e_dir / "e2e_input.json"),
            "result_path": str(e2e_dir / "e2e_result.json"),
            "summary_path": str(e2e_dir / "e2e_summary.json"),
            "artifacts_manifest_path": str(e2e_dir / "e2e_artifacts_manifest.json"),
        }

    def _run(self, request: XhsE2EReplayRequest) -> XhsE2EReplayResult:
        paths = self.get_e2e_paths(request.run_id)
        steps: list[XhsE2EReplayStepResult] = []
        artifacts: list[str] = []
        status = "success"
        error_code = None
        error_message = None
        summary_state = {
            "readiness_status": None,
            "strict_binding_status": None,
            "hardened_discovery_status": None,
            "contract_replay_status": None,
            "persistence_replay_status": None,
        }
        try:
            input_payload = self.build_e2e_input(request)
            input_path = self.write_e2e_input(request.run_id, input_payload)
            artifacts.append(input_path)

            readiness = self.run_readiness_check()
            summary_state["readiness_status"] = readiness.get("status")
            steps.append(XhsE2EReplayStepResult(step_name="readiness", status="success", output_path=input_path))

            hardened = self.run_or_load_hardened_discovery()
            summary_state["hardened_discovery_status"] = hardened.get("status")
            steps.append(XhsE2EReplayStepResult(step_name="hardened_discovery", status="success", output_path=hardened.get("hardened_discovery_path")))
            artifacts.append(str(hardened.get("hardened_discovery_path")))

            if request.job_type in {"search", "all"}:
                strict = self.run_or_load_strict_binding("search", request)
                summary_state["strict_binding_status"] = strict.get("binding_status")
                steps.append(XhsE2EReplayStepResult(step_name="search_strict_binding", status="success", output_path=strict.get("strict_binding_result_path"), summary_path=strict.get("strict_binding_summary_path")))
                artifacts.extend([strict.get("strict_binding_result_path"), strict.get("strict_binding_summary_path")])
                contract = self.run_contract_replay_search(request)
                summary_state["contract_replay_status"] = contract.get("status")
                steps.append(XhsE2EReplayStepResult(step_name="search_contract_replay", status="success"))
                artifacts.extend(self._collect_contract_artifacts(contract))
                persistence = self.run_persistence_replay_search(request)
                summary_state["persistence_replay_status"] = persistence.get("status")
                steps.append(XhsE2EReplayStepResult(step_name="search_persistence_replay", status="success", output_path=persistence.get("result_path"), summary_path=persistence.get("summary_path")))
                artifacts.extend(self._collect_persistence_artifacts(persistence))

            if request.job_type in {"publish", "all"}:
                strict = self.run_or_load_strict_binding("publish", request)
                summary_state["strict_binding_status"] = strict.get("binding_status")
                steps.append(XhsE2EReplayStepResult(step_name="publish_strict_binding", status="success", output_path=strict.get("strict_binding_result_path"), summary_path=strict.get("strict_binding_summary_path")))
                artifacts.extend([strict.get("strict_binding_result_path"), strict.get("strict_binding_summary_path")])
                contract = self.run_contract_replay_publish(request)
                summary_state["contract_replay_status"] = contract.get("status")
                steps.append(XhsE2EReplayStepResult(step_name="publish_contract_replay", status="success"))
                artifacts.extend(self._collect_contract_artifacts(contract))
                persistence = self.run_persistence_replay_publish(request)
                summary_state["persistence_replay_status"] = persistence.get("status")
                steps.append(XhsE2EReplayStepResult(step_name="publish_persistence_replay", status="success", output_path=persistence.get("result_path"), summary_path=persistence.get("summary_path")))
                artifacts.extend(self._collect_persistence_artifacts(persistence))

        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            steps.append(XhsE2EReplayStepResult(step_name="failed_step", status="failed", error_code=exc.error_code, error_message=exc.error_message))
            if not Path(paths["input_path"]).exists():
                input_path = self.write_e2e_input(
                    request.run_id,
                    {
                        "schema_version": "1.0",
                        "replay_type": "local_full_e2e_replay",
                        "run_id": request.run_id,
                        "job_type": request.job_type,
                        "account_id": request.account_id,
                        "safe_mode": True,
                        "input_write_limited": exc.error_code == XHS_E2E_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
                        "forbidden": self._forbidden_actions(),
                    },
                )
                artifacts.append(input_path)

        artifacts = [path for path in artifacts if path]
        manifest = self.build_artifacts_manifest(request.run_id, request.job_type, artifacts)
        manifest_path = self.write_artifacts_manifest(request.run_id, manifest)
        artifacts.append(manifest_path)
        scan = self.scan_sensitive_artifacts(manifest)
        result = XhsE2EReplayResult(
            run_id=request.run_id,
            job_type=request.job_type,
            status=status,
            steps=steps,
            e2e_input_path=paths["input_path"],
            e2e_result_path=paths["result_path"],
            e2e_summary_path=paths["summary_path"],
            artifacts_manifest_path=manifest_path,
            sensitive_payload_detected=not scan["passed"],
            external_call_forbidden=True,
            error_code=error_code,
            error_message=error_message,
        )
        summary = XhsE2EReplaySummary(
            run_id=request.run_id,
            job_type=request.job_type,
            status=status,
            generated_artifacts=artifacts,
            forbidden_actions=self._forbidden_actions(),
            sensitive_scan=scan,
            created_at=self._utc_now(),
            error_code=error_code,
            error_message=error_message,
            **summary_state,
        )
        result_path = self.write_e2e_result(request.run_id, self._model_to_dict(result))
        summary_path = self.write_e2e_summary(request.run_id, self._model_to_dict(summary))
        result.e2e_result_path = result_path
        result.e2e_summary_path = summary_path
        self.write_e2e_result(request.run_id, self._model_to_dict(result))
        return result

    def _collect_contract_artifacts(self, payload: dict[str, Any]) -> list[str]:
        artifacts: list[str] = []
        for section in ("n8n_replay", "openclaw_replay"):
            item = payload.get(section) or {}
            artifacts.extend([item.get("replay_payload_path"), item.get("replay_result_path"), item.get("replay_summary_path")])
        return [path for path in artifacts if path]

    def _collect_persistence_artifacts(self, payload: dict[str, Any]) -> list[str]:
        artifacts = [payload.get("result_path"), payload.get("summary_path")]
        for section in ("feishu", "postgres", "minio"):
            item = payload.get(section) or {}
            artifacts.extend([item.get("payload_path"), item.get("result_path"), item.get("summary_path")])
        return [path for path in artifacts if path]

    def _forbidden_actions(self) -> dict[str, bool]:
        return {
            "real_feishu_write": True,
            "real_postgres_write": True,
            "real_minio_upload": True,
            "external_n8n_call": True,
            "external_openclaw_call": True,
            "yingdao_openapi": True,
            "open_shop": True,
            "open_xhs": True,
            "open_external_webpage": True,
            "real_search": True,
            "real_publish": True,
        }

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(XHS_E2E_REPLAY_ERROR, f"failed to write E2E replay JSON: {path}: {exc}") from exc

    def _resolve_worker_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
