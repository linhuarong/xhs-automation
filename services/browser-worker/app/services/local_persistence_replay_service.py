import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    XhsFeishuMockPersistencePayload,
    XhsMinioMockObjectManifest,
    XhsPersistenceReplayAllResult,
    XhsPersistenceReplayResult,
    XhsPersistenceReplaySummary,
    XhsPostgresMockPersistencePayload,
)
from app.services.local_contract_replay_service import LocalContractReplayService
from app.services.xhs_account_binding_service import XhsAccountBindingService
from app.utils.errors import (
    XHS_PERSISTENCE_REPLAY_ERROR,
    XHS_PERSISTENCE_REPLAY_EXTERNAL_WRITE_FORBIDDEN,
    XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_MISSING,
    XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_UNSAFE,
    XHS_PERSISTENCE_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
    XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_INVALID,
    XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_MISSING,
    XHS_PERSISTENCE_REPLAY_STRICT_BINDING_FAILED,
    XHS_PERSISTENCE_REPLAY_STRICT_BINDING_MISSING,
    XHS_PERSISTENCE_REPLAY_TARGET_UNSUPPORTED,
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


class LocalPersistenceReplayService:
    """Build local Feishu/PostgreSQL/MinIO mock persistence replay packages."""

    def __init__(
        self,
        contract_replay_service: LocalContractReplayService | None = None,
        account_binding_service: XhsAccountBindingService | None = None,
        persistence_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.account_binding_service = account_binding_service or XhsAccountBindingService(worker_root=self.worker_root)
        self.contract_replay_service = contract_replay_service or LocalContractReplayService(
            account_binding_service=self.account_binding_service,
            worker_root=self.worker_root,
        )
        self.persistence_root = self._resolve_worker_path(
            persistence_root or os.getenv("XHS_LOCAL_PERSISTENCE_REPLAY_ROOT", ".local_rpa_queue/persistence")
        )

    def replay_feishu_mock(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
        source_replay_result_path: str | None = None,
        source_replay_summary_path: str | None = None,
    ) -> XhsPersistenceReplayResult:
        """Generate local Feishu mock persistence payload/result/summary."""
        context = self._load_required_context(job_id, job_type, source_replay_result_path, source_replay_summary_path)
        payload = self.build_feishu_mock_payload(job_id, context["job_type"], account_id, context)
        return self._write_target_package("feishu", job_id, context["job_type"], payload)

    def replay_postgres_mock(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
        source_replay_result_path: str | None = None,
        source_replay_summary_path: str | None = None,
    ) -> XhsPersistenceReplayResult:
        """Generate local PostgreSQL mock persistence payload/result/summary."""
        context = self._load_required_context(job_id, job_type, source_replay_result_path, source_replay_summary_path)
        payload = self.build_postgres_mock_payload(job_id, context["job_type"], account_id, context)
        return self._write_target_package("postgres", job_id, context["job_type"], payload)

    def replay_minio_mock(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
        source_replay_result_path: str | None = None,
        source_replay_summary_path: str | None = None,
    ) -> XhsPersistenceReplayResult:
        """Generate local MinIO mock object manifest/result/summary."""
        context = self._load_required_context(job_id, job_type, source_replay_result_path, source_replay_summary_path)
        manifest = self.build_minio_object_manifest(job_id, context["job_type"], account_id, context)
        return self._write_target_package("minio", job_id, context["job_type"], manifest)

    def replay_all_for_job(self, job_id: str, job_type: str, account_id: str) -> XhsPersistenceReplayAllResult:
        """Run all local mock persistence targets for one job."""
        normalized = self._normalize_job_type(job_type)
        try:
            feishu = self.replay_feishu_mock(job_id, normalized, account_id)
            postgres = self.replay_postgres_mock(job_id, normalized, account_id)
            minio = self.replay_minio_mock(job_id, normalized, account_id)
            status = "success" if all(item.status == "success" for item in [feishu, postgres, minio]) else "failed"
            paths = self.get_persistence_paths("all", normalized, job_id)
            result = XhsPersistenceReplayAllResult(
                job_id=job_id,
                job_type=normalized,
                status=status,
                feishu=self._model_to_dict(feishu),
                postgres=self._model_to_dict(postgres),
                minio=self._model_to_dict(minio),
                result_path=paths["result_path"],
                summary_path=paths["summary_path"],
            )
            result_path = self.write_persistence_result("all", normalized, job_id, self._model_to_dict(result))
            summary = XhsPersistenceReplaySummary(
                job_id=job_id,
                job_type=normalized,
                targets=["feishu", "postgres", "minio"],
                status=status,
                strict_binding_status=feishu.strict_binding_status,
                hardened_discovery_status=feishu.hardened_discovery_status,
                source_replay_status=feishu.source_replay_status,
                generated_payloads=[
                    path
                    for path in [feishu.payload_path, postgres.payload_path, minio.payload_path]
                    if path
                ],
                generated_results=[
                    path
                    for path in [feishu.result_path, postgres.result_path, minio.result_path, result_path]
                    if path
                ],
                forbidden_actions=self._forbidden_actions(),
                sensitive_scan={"passed": True, "matches": []},
                created_at=self._utc_now(),
            )
            summary_path = self.write_persistence_summary("all", normalized, job_id, self._model_to_dict(summary))
            result.result_path = result_path
            result.summary_path = summary_path
            self.write_persistence_result("all", normalized, job_id, self._model_to_dict(result))
            return result
        except WorkerError as exc:
            paths = self.get_persistence_paths("all", normalized, job_id)
            result = XhsPersistenceReplayAllResult(
                job_id=job_id,
                job_type=normalized,
                status="failed",
                result_path=paths["result_path"],
                summary_path=paths["summary_path"],
                error_code=exc.error_code,
                error_message=exc.error_message,
            )
            self.write_persistence_result("all", normalized, job_id, self._model_to_dict(result))
            summary = XhsPersistenceReplaySummary(
                job_id=job_id,
                job_type=normalized,
                targets=["all"],
                status="failed",
                generated_results=[paths["result_path"]],
                forbidden_actions=self._forbidden_actions(),
                sensitive_scan={"passed": True, "matches": []},
                created_at=self._utc_now(),
                error_code=exc.error_code,
                error_message=exc.error_message,
            )
            self.write_persistence_summary("all", normalized, job_id, self._model_to_dict(summary))
            return result

    def load_contract_replay_result(self, job_type: str, job_id: str, source_path: str | None = None) -> dict[str, Any]:
        """Load Task 38 n8n replay_result.json."""
        path = self._source_contract_path("result_path", job_type, job_id, source_path)
        if not path.exists():
            raise WorkerError(XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_MISSING, f"source contract replay result not found: {path}")
        payload = self._read_json(path, XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_INVALID)
        if payload.get("status") != "success" or payload.get("replay_type") != "local_contract_replay_result":
            raise WorkerError(XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_INVALID, "source contract replay result is not successful")
        return payload | {"_path": str(path)}

    def load_contract_replay_summary(self, job_type: str, job_id: str, source_path: str | None = None) -> dict[str, Any]:
        """Load Task 38 n8n replay_summary.json."""
        path = self._source_contract_path("summary_path", job_type, job_id, source_path)
        if not path.exists():
            raise WorkerError(XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_MISSING, f"source contract replay summary not found: {path}")
        payload = self._read_json(path, XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_INVALID)
        if payload.get("status") != "success" or payload.get("summary_type") != "local_contract_replay_summary":
            raise WorkerError(XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_INVALID, "source contract replay summary is not successful")
        return payload | {"_path": str(path)}

    def load_strict_binding_context(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Load strict account binding result and convert it to persistence context."""
        path = Path(self.account_binding_service.get_strict_binding_paths(job_type, job_id)["result_path"])
        if not path.exists():
            raise WorkerError(XHS_PERSISTENCE_REPLAY_STRICT_BINDING_MISSING, f"strict binding result not found: {path}")
        payload = self._read_json(path, XHS_PERSISTENCE_REPLAY_STRICT_BINDING_FAILED)
        if payload.get("status") != "success" or payload.get("binding_status") != "strict_matched":
            raise WorkerError(
                XHS_PERSISTENCE_REPLAY_STRICT_BINDING_FAILED,
                f"strict binding is not strict_matched: {payload.get('binding_status')}",
            )
        profile = payload.get("matched_profile") or {}
        shop = payload.get("matched_shop") or {}
        return {
            "binding_status": payload.get("binding_status"),
            "strict_binding_result_path": str(path),
            "account_id": payload.get("account_id"),
            "shop_id": profile.get("shop_id") or shop.get("shop_id"),
            "shop_name": profile.get("shop_name") or shop.get("shop_name"),
            "provider_type": profile.get("provider_type") or "kuaijingvs_yingdao_rpa",
        }

    def load_hardened_discovery_reference(self) -> dict[str, Any]:
        """Load hardened discovery and return a safe reference only."""
        path = Path(self.account_binding_service.hardened_discovery_path)
        if not path.exists():
            raise WorkerError(XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_MISSING, f"hardened discovery not found: {path}")
        payload = self._read_json(path, XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_UNSAFE)
        safe = (
            payload.get("status") == "success"
            and bool((payload.get("sanitization") or {}).get("sensitive_value_scan_passed"))
            and not any((payload.get("forbidden") or {}).values())
            and not (payload.get("errors") or [])
            and bool(payload.get("evidence_hash"))
        )
        if not safe:
            raise WorkerError(XHS_PERSISTENCE_REPLAY_HARDENED_DISCOVERY_UNSAFE, "hardened discovery is unsafe for persistence replay")
        return {
            "hardened_discovery_path": str(path),
            "evidence_hash": payload.get("evidence_hash"),
            "status": payload.get("status"),
            "safe": True,
            "shop_count": payload.get("shop_count", len(payload.get("shops") or [])),
        }

    def build_feishu_mock_payload(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build local-only Feishu mock persistence payload."""
        normalized = self._normalize_job_type(job_type)
        replay_payload = context.get("source_replay_payload") or {}
        source_payload = replay_payload.get("payload") or {}
        if normalized == "search":
            fields = {
                "关键词": source_payload.get("keyword"),
                "account_id": account_id,
                "job_id": job_id,
                "provider_type": context["strict_binding_context"].get("provider_type"),
                "strict_binding_status": context["strict_binding_context"].get("binding_status"),
                "hardened_discovery_status": context["hardened_discovery_reference"].get("status"),
                "replay_status": context["source_replay_reference"].get("source_replay_status"),
                "result_count": 0,
                "normalized_record_count": 0,
                "evidence_json_path": self._mock_evidence_path("search", job_id),
                "screenshot_path": self._mock_screenshot_path("search", job_id),
                "处理状态": "mock_persisted",
                "错误码": None,
                "错误信息": None,
            }
            target_table = "xhs_search_hotspot_pool_mock"
        else:
            fields = {
                "标题": source_payload.get("title"),
                "正文": source_payload.get("body"),
                "标签": source_payload.get("tags") or [],
                "图片路径": source_payload.get("image_paths") or [],
                "account_id": account_id,
                "job_id": job_id,
                "publish_mode": source_payload.get("publish_mode") or "manual_review",
                "strict_binding_status": context["strict_binding_context"].get("binding_status"),
                "hardened_discovery_status": context["hardened_discovery_reference"].get("status"),
                "replay_status": context["source_replay_reference"].get("source_replay_status"),
                "发布状态": "mock_persisted",
                "note_url": None,
                "错误码": None,
                "错误信息": None,
            }
            target_table = "xhs_publish_pool_mock"
        payload = XhsFeishuMockPersistencePayload(
            job_id=job_id,
            job_type=normalized,
            account_id=account_id,
            target_table=target_table,
            fields=fields,
            strict_binding_context=context["strict_binding_context"],
            hardened_discovery_reference=context["hardened_discovery_reference"],
            source_replay_reference=context["source_replay_reference"],
        )
        return self.sanitize_persistence_payload(self._model_to_dict(payload))

    def build_postgres_mock_payload(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build local-only PostgreSQL mock persistence payload."""
        normalized = self._normalize_job_type(job_type)
        replay_payload = context.get("source_replay_payload") or {}
        source_payload = replay_payload.get("payload") or {}
        if normalized == "search":
            tables = ["xhs_search_evidence", "xhs_search_records", "xhs_task_log", "xhs_workflow_log"]
            rows = [
                {"table": "xhs_search_evidence", "job_id": job_id, "account_id": account_id, "evidence_json_path": self._mock_evidence_path("search", job_id)},
                {"table": "xhs_search_records", "job_id": job_id, "keyword": source_payload.get("keyword"), "normalized_record_count": 0},
                {"table": "xhs_task_log", "job_id": job_id, "status": "mock_persisted"},
                {"table": "xhs_workflow_log", "job_id": job_id, "workflow": "local_persistence_replay"},
            ]
        else:
            tables = ["xhs_publish_evidence", "xhs_publish_jobs", "xhs_task_log", "xhs_workflow_log"]
            rows = [
                {"table": "xhs_publish_evidence", "job_id": job_id, "account_id": account_id, "evidence_json_path": self._mock_evidence_path("publish", job_id)},
                {"table": "xhs_publish_jobs", "job_id": job_id, "title": source_payload.get("title"), "publish_mode": source_payload.get("publish_mode")},
                {"table": "xhs_task_log", "job_id": job_id, "status": "mock_persisted"},
                {"table": "xhs_workflow_log", "job_id": job_id, "workflow": "local_persistence_replay"},
            ]
        payload = XhsPostgresMockPersistencePayload(
            job_id=job_id,
            job_type=normalized,
            account_id=account_id,
            target_tables=tables,
            operation_plan=[{"table": table, "operation": "mock_upsert"} for table in tables],
            rows=rows,
            strict_binding_context=context["strict_binding_context"],
            hardened_discovery_reference=context["hardened_discovery_reference"],
            source_replay_reference=context["source_replay_reference"],
        )
        return self.sanitize_persistence_payload(self._model_to_dict(payload))

    def build_minio_object_manifest(
        self,
        job_id: str,
        job_type: str,
        account_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build local-only MinIO mock object manifest."""
        normalized = self._normalize_job_type(job_type)
        prefix = f"mock/{normalized}/{job_id}"
        if normalized == "search":
            objects = [
                {"object_key": f"{prefix}/search_evidence.json", "source_path": self._mock_evidence_path("search", job_id), "purpose": "search evidence json"},
                {"object_key": f"{prefix}/search_screenshot.png", "source_path": self._mock_screenshot_path("search", job_id), "purpose": "search screenshot"},
                {"object_key": f"{prefix}/replay_payload.json", "source_path": context["source_replay_reference"].get("payload_path"), "purpose": "replay payload"},
                {"object_key": f"{prefix}/replay_summary.json", "source_path": context["source_replay_reference"].get("summary_path"), "purpose": "replay summary"},
                {"object_key": f"{prefix}/persistence_summary.json", "source_path": None, "purpose": "persistence summary"},
            ]
        else:
            objects = [
                {"object_key": f"{prefix}/publish_evidence.json", "source_path": self._mock_evidence_path("publish", job_id), "purpose": "publish evidence json"},
                {"object_key": f"{prefix}/publish_screenshot_001.png", "source_path": self._mock_screenshot_path("publish", job_id), "purpose": "publish screenshot"},
                {"object_key": f"{prefix}/publish_asset_001.png", "source_path": self._first_image_path(context), "purpose": "publish asset reference"},
                {"object_key": f"{prefix}/replay_payload.json", "source_path": context["source_replay_reference"].get("payload_path"), "purpose": "replay payload"},
                {"object_key": f"{prefix}/replay_summary.json", "source_path": context["source_replay_reference"].get("summary_path"), "purpose": "replay summary"},
                {"object_key": f"{prefix}/persistence_summary.json", "source_path": None, "purpose": "persistence summary"},
            ]
        manifest = XhsMinioMockObjectManifest(
            job_id=job_id,
            job_type=normalized,
            account_id=account_id,
            object_prefix=prefix,
            objects=objects,
            strict_binding_context=context["strict_binding_context"],
            hardened_discovery_reference=context["hardened_discovery_reference"],
            source_replay_reference=context["source_replay_reference"],
        )
        return self.sanitize_persistence_payload(self._model_to_dict(manifest))

    def sanitize_persistence_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Reject sensitive fields/values before writing persistence replay payloads."""
        scan = self.scan_sensitive_payload(payload)
        if not scan["passed"]:
            raise WorkerError(
                XHS_PERSISTENCE_REPLAY_SENSITIVE_PAYLOAD_DETECTED,
                f"persistence replay payload contains sensitive content: {', '.join(scan['matches'])}",
            )
        return payload

    def scan_sensitive_payload(self, payload: Any) -> dict[str, Any]:
        """Scan payload keys and values for secret-like content."""
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

    def validate_no_external_write(self, target: str) -> bool:
        """Guard against accidentally enabling real persistence writes for Task 39."""
        target = str(target).lower()
        flag_by_target = {
            "feishu": "XHS_LOCAL_PERSISTENCE_ALLOW_REAL_FEISHU",
            "postgres": "XHS_LOCAL_PERSISTENCE_ALLOW_REAL_POSTGRES",
            "minio": "XHS_LOCAL_PERSISTENCE_ALLOW_REAL_MINIO",
        }
        flag = flag_by_target.get(target)
        if not flag:
            raise WorkerError(XHS_PERSISTENCE_REPLAY_TARGET_UNSUPPORTED, f"unsupported persistence target: {target}")
        if self._truthy(os.getenv(flag, "false")):
            raise WorkerError(XHS_PERSISTENCE_REPLAY_EXTERNAL_WRITE_FORBIDDEN, f"real {target} writes are forbidden in local persistence replay")
        return True

    def write_persistence_payload(self, target: str, job_type: str, job_id: str, payload: dict[str, Any]) -> str:
        """Write persistence_payload.json."""
        return self._write_json(Path(self.get_persistence_paths(target, job_type, job_id)["payload_path"]), payload)

    def write_object_manifest(self, job_type: str, job_id: str, manifest: dict[str, Any]) -> str:
        """Write MinIO object_manifest.json."""
        return self._write_json(Path(self.get_persistence_paths("minio", job_type, job_id)["payload_path"]), manifest)

    def write_persistence_result(self, target: str, job_type: str, job_id: str, result: dict[str, Any]) -> str:
        """Write persistence_result.json."""
        return self._write_json(Path(self.get_persistence_paths(target, job_type, job_id)["result_path"]), result)

    def write_persistence_summary(self, target: str, job_type: str, job_id: str, summary: dict[str, Any]) -> str:
        """Write persistence_summary.json."""
        return self._write_json(Path(self.get_persistence_paths(target, job_type, job_id)["summary_path"]), summary)

    def get_persistence_paths(self, target: str, job_type: str, job_id: str) -> dict[str, str]:
        """Return local persistence replay paths."""
        normalized = self._normalize_job_type(job_type)
        target = str(target).strip().lower()
        if target not in {"feishu", "postgres", "minio", "all"}:
            raise WorkerError(XHS_PERSISTENCE_REPLAY_TARGET_UNSUPPORTED, f"unsupported persistence target: {target}")
        replay_dir = self.persistence_root / target / normalized / job_id
        payload_name = "object_manifest.json" if target == "minio" else "persistence_payload.json"
        return {
            "persistence_dir": str(replay_dir),
            "payload_path": str(replay_dir / payload_name),
            "result_path": str(replay_dir / "persistence_result.json"),
            "summary_path": str(replay_dir / "persistence_summary.json"),
        }

    def _write_target_package(self, target: str, job_id: str, job_type: str, payload: dict[str, Any]) -> XhsPersistenceReplayResult:
        normalized = self._normalize_job_type(job_type)
        self.validate_no_external_write(target)
        scan = self.scan_sensitive_payload(payload)
        if not scan["passed"]:
            raise WorkerError(XHS_PERSISTENCE_REPLAY_SENSITIVE_PAYLOAD_DETECTED, f"persistence payload contains sensitive content: {scan['matches']}")
        if target == "minio":
            payload_path = self.write_object_manifest(normalized, job_id, payload)
        else:
            payload_path = self.write_persistence_payload(target, normalized, job_id, payload)
        result = XhsPersistenceReplayResult(
            job_id=job_id,
            job_type=normalized,
            target=target,
            status="success",
            payload_path=payload_path,
            result_path=self.get_persistence_paths(target, normalized, job_id)["result_path"],
            summary_path=self.get_persistence_paths(target, normalized, job_id)["summary_path"],
            sensitive_payload_detected=False,
            external_write_forbidden=True,
            strict_binding_status=(payload.get("strict_binding_context") or {}).get("binding_status"),
            hardened_discovery_status=(payload.get("hardened_discovery_reference") or {}).get("status"),
            source_replay_status=(payload.get("source_replay_reference") or {}).get("source_replay_status"),
        )
        result_path = self.write_persistence_result(target, normalized, job_id, self._model_to_dict(result))
        summary = XhsPersistenceReplaySummary(
            job_id=job_id,
            job_type=normalized,
            targets=[target],
            status="success",
            strict_binding_status=result.strict_binding_status,
            hardened_discovery_status=result.hardened_discovery_status,
            source_replay_status=result.source_replay_status,
            generated_payloads=[payload_path],
            generated_results=[result_path],
            forbidden_actions=self._forbidden_actions(),
            sensitive_scan=scan,
            created_at=self._utc_now(),
        )
        summary_path = self.write_persistence_summary(target, normalized, job_id, self._model_to_dict(summary))
        result.result_path = result_path
        result.summary_path = summary_path
        self.write_persistence_result(target, normalized, job_id, self._model_to_dict(result))
        return result

    def _load_required_context(
        self,
        job_id: str,
        job_type: str,
        source_replay_result_path: str | None,
        source_replay_summary_path: str | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_job_type(job_type)
        result = self.load_contract_replay_result(normalized, job_id, source_replay_result_path)
        summary = self.load_contract_replay_summary(normalized, job_id, source_replay_summary_path)
        strict = self.load_strict_binding_context(normalized, job_id)
        hardened = self.load_hardened_discovery_reference()
        payload_path = self._source_contract_path("payload_path", normalized, job_id, None)
        replay_payload = self._read_json(payload_path, XHS_PERSISTENCE_REPLAY_SOURCE_CONTRACT_INVALID) if payload_path.exists() else {}
        source_reference = {
            "result_path": result.get("_path"),
            "summary_path": summary.get("_path"),
            "payload_path": str(payload_path) if payload_path.exists() else None,
            "target": result.get("target"),
            "local_route": result.get("local_route"),
            "source_replay_status": result.get("status"),
            "summary_status": summary.get("status"),
        }
        return {
            "job_type": normalized,
            "source_replay_result": result,
            "source_replay_summary": summary,
            "source_replay_payload": replay_payload,
            "source_replay_reference": source_reference,
            "strict_binding_context": strict,
            "hardened_discovery_reference": hardened,
        }

    def _source_contract_path(self, key: str, job_type: str, job_id: str, explicit_path: str | None) -> Path:
        if explicit_path:
            return self._resolve_worker_path(explicit_path)
        normalized = self._normalize_job_type(job_type)
        target = "n8n_mock_search_webhook" if normalized == "search" else "n8n_mock_publish_webhook"
        return Path(self.contract_replay_service.get_replay_paths(target, normalized, job_id)[key])

    def _mock_evidence_path(self, job_type: str, job_id: str) -> str:
        return f".local_rpa_queue/replay/n8n/{job_type}/{job_id}/replay_result.json"

    def _mock_screenshot_path(self, job_type: str, job_id: str) -> str:
        return f".local_evidence/{job_type}/{job_id}/screenshot_mock.png"

    def _first_image_path(self, context: dict[str, Any]) -> str | None:
        payload = context.get("source_replay_payload") or {}
        images = (payload.get("payload") or {}).get("image_paths") or []
        return images[0] if images else None

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
            "real_search": True,
            "real_publish": True,
        }

    def _read_json(self, path: Path, error_code: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(error_code, f"JSON file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(error_code, f"JSON file invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(error_code, f"JSON file must contain an object: {path}")
        return payload

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(XHS_PERSISTENCE_REPLAY_ERROR, f"failed to write persistence replay JSON: {path}: {exc}") from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "search"
        if normalized in {"publish", "xhs_publish"}:
            return "publish"
        raise WorkerError(XHS_PERSISTENCE_REPLAY_ERROR, f"unsupported persistence replay job_type: {job_type}")

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

    def _truthy(self, value: str | bool | None) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
