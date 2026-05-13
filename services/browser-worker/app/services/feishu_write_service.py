import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib import request as urllib_request

from app.schemas import (
    XhsFeishuReadbackCheck,
    XhsFeishuReadbackRequest,
    XhsFeishuReadbackSummary,
    XhsFeishuWritePayload,
    XhsFeishuWritePlan,
    XhsFeishuWritePlanItem,
    XhsFeishuWriteRequest,
    XhsFeishuWriteResult,
    XhsFeishuWriteSummary,
)
from app.utils.errors import (
    FEISHU_CONFIG_MISSING,
    FEISHU_FIELD_MAPPING_MISMATCH,
    FEISHU_PAYLOAD_INVALID,
    FEISHU_READBACK_DISABLED,
    FEISHU_READBACK_FAILED,
    FEISHU_READBACK_MARKER_REQUIRED,
    FEISHU_READBACK_RECORD_ID_REQUIRED,
    FEISHU_RECORD_ID_REQUIRED,
    FEISHU_SENSITIVE_VALUE_BLOCKED,
    FEISHU_WRITE_DISABLED,
    FEISHU_WRITE_FAILED,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "tenant_access_token",
    "user_access_token",
    "cookie",
    "set-cookie",
    "secret",
    "app_secret",
    "password",
    "passwd",
    "authorization",
    "auth",
    "api_key",
    "header",
    "headers",
    "session",
    "credential",
    "private_key",
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
        r"\.env",
        r"\.config[\\/]",
        r"profile",
        r"localStorage",
        r"app_secret",
    )
]
SEARCH_FIELD_MAPPING = {
    "job_id": "任务ID",
    "keyword": "关键词",
    "account_id": "账号ID",
    "provider_type": "Provider",
    "rank": "排名",
    "title": "标题",
    "author": "作者",
    "published_at_text": "发布时间文本",
    "note_id": "笔记ID",
    "note_url": "笔记链接",
    "metric_raw_text": "指标原文",
    "like_count_text": "点赞数文本",
    "screenshot_path": "截图路径",
    "evidence_json_path": "Evidence路径",
    "minio_screenshot_url": "MinIO截图URL",
    "minio_evidence_url": "MinIO Evidence URL",
    "status": "状态",
    "error_code": "错误码",
    "error_message": "错误信息",
    "captured_at": "捕获时间",
}
PUBLISH_FIELD_MAPPING = {
    "job_id": "任务ID",
    "account_id": "账号ID",
    "provider_type": "Provider",
    "title": "标题",
    "body_summary": "正文摘要",
    "tags": "标签",
    "status": "发布状态",
    "note_url": "笔记链接",
    "evidence_json_path": "Evidence路径",
    "minio_evidence_url": "MinIO Evidence URL",
    "publish_before_url": "发布前截图URL",
    "publish_form_filled_url": "表单截图URL",
    "publish_result_url": "结果截图URL",
    "error_code": "错误码",
    "error_message": "错误信息",
    "updated_at": "更新时间",
}


class FeishuWriteService:
    """Controlled Feishu phase-1 writer with dry-run-first outputs."""

    def __init__(
        self,
        worker_root: str | Path | None = None,
        output_root: str | Path | None = None,
        env: dict[str, str] | None = None,
        http_client: Callable[[str, str, dict[str, str], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.env = env
        self.http_client = http_client
        self.output_root = self._resolve_worker_path(
            output_root or self._get("XHS_FEISHU_WRITE_OUTPUT_ROOT", ".local_rpa_queue/feishu_write")
        )
        self.readback_output_root = self._resolve_worker_path(
            self._get("XHS_FEISHU_READBACK_OUTPUT_ROOT", ".local_rpa_queue/feishu_readback")
        )

    def plan_or_write_search(self, request: XhsFeishuWriteRequest) -> XhsFeishuWriteResult:
        """Plan or explicitly write search records to Feishu."""
        return self._run(request.model_copy(update={"job_type": "search"}))

    def plan_or_write_publish(self, request: XhsFeishuWriteRequest) -> XhsFeishuWriteResult:
        """Plan or explicitly write publish status records to Feishu."""
        return self._run(request.model_copy(update={"job_type": "publish"}))

    def get_feishu_write_enabled(self) -> bool:
        """Return whether the Feishu write adapter is enabled."""
        return self._truthy(self._get("XHS_FEISHU_WRITE_ENABLED", "false"))

    def get_real_write_allowed(self, request: XhsFeishuWriteRequest) -> bool:
        """Return whether this request is allowed to perform real Feishu writes."""
        return (
            not request.dry_run
            and request.operation in {"create", "update"}
            and self.get_feishu_write_enabled()
            and self._truthy(self._get("XHS_ALLOW_REAL_FEISHU_WRITE", "false"))
            and self._feishu_configured(request)
        )

    def get_feishu_readback_enabled(self) -> bool:
        """Return whether controlled Feishu readback is enabled."""
        return self._truthy(self._get("XHS_FEISHU_READBACK_ENABLED", "false"))

    def get_real_readback_allowed(self, request: XhsFeishuReadbackRequest) -> bool:
        """Return whether this request may perform a real single-record readback."""
        write_request = XhsFeishuWriteRequest(
            job_id=request.job_id,
            job_type=request.job_type,
            account_id=request.account_id,
            operation="update" if request.operation == "update" else "create",
            feishu_record_id=request.feishu_record_id,
            dry_run=request.dry_run,
            table_id=request.table_id,
            app_token=request.app_token,
        )
        return (
            not request.dry_run
            and self.get_feishu_readback_enabled()
            and self._truthy(self._get("XHS_FEISHU_SMOKE_ENABLED", "false"))
            and self.get_real_write_allowed(write_request)
            and bool(request.feishu_record_id)
        )

    def resolve_target_table(self, job_type: str, request: XhsFeishuWriteRequest) -> dict[str, Any]:
        """Resolve target table without returning sensitive values."""
        normalized = self._normalize_job_type(job_type)
        table_env = "XHS_FEISHU_SEARCH_TABLE_ID" if normalized == "search" else "XHS_FEISHU_PUBLISH_TABLE_ID"
        table_id = request.table_id or self._get(table_env)
        app_token = request.app_token or self._get("XHS_FEISHU_APP_TOKEN")
        return {
            "target_table_kind": "search_hotspot_pool" if normalized == "search" else "publish_status_pool",
            "table_id": table_id,
            "app_token": app_token,
            "table_id_configured": self._value_configured(table_id),
            "app_token_configured": self._value_configured(app_token),
        }

    def load_source_records(self, request: XhsFeishuWriteRequest) -> list[dict[str, Any]]:
        """Load records from request records or a local source result file."""
        if request.records is not None:
            return [dict(record) for record in request.records]
        if request.source_result_path:
            source_path = self._resolve_worker_path(request.source_result_path)
            try:
                payload = json.loads(source_path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise WorkerError(FEISHU_PAYLOAD_INVALID, f"Feishu source result not found: {source_path}") from exc
            except json.JSONDecodeError as exc:
                raise WorkerError(FEISHU_PAYLOAD_INVALID, f"Feishu source result invalid: {source_path}: {exc}") from exc
            if not isinstance(payload, dict):
                raise WorkerError(FEISHU_PAYLOAD_INVALID, "Feishu source result must be a JSON object")
            for key in ("normalized_records", "records", "items"):
                if isinstance(payload.get(key), list):
                    return [dict(item) for item in payload[key] if isinstance(item, dict)]
            nested = payload.get("result")
            if isinstance(nested, dict):
                for key in ("normalized_records", "records", "items"):
                    if isinstance(nested.get(key), list):
                        return [dict(item) for item in nested[key] if isinstance(item, dict)]
            return [payload]
        return [
            {
                "job_id": request.job_id,
                "account_id": request.account_id,
                "status": "dry_run_planned",
            }
        ]

    def sanitize_feishu_field_value(self, value: Any) -> Any:
        """Sanitize values before they enter Feishu writable fields."""
        if value is None or isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, list):
            return ", ".join(str(self.sanitize_feishu_field_value(item)) for item in value if item is not None)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        text = str(value)
        if self._looks_like_absolute_path(text):
            return self._safe_path_value(text)
        return text[:2000]

    def scan_payload_for_sensitive_values(self, payload: Any) -> dict[str, Any]:
        """Scan Feishu plan/payload for sensitive keys and values."""
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

    def build_search_hotspot_fields(self, record: dict[str, Any], request: XhsFeishuWriteRequest) -> dict[str, Any]:
        """Build Feishu hotspot-pool fields for one normalized search record."""
        merged = dict(record)
        merged.setdefault("job_id", request.job_id)
        merged.setdefault("account_id", request.account_id)
        merged.setdefault("provider_type", record.get("provider_type") or "kuaijingvs_yingdao_rpa")
        merged.setdefault("status", record.get("status") or "dry_run_planned")
        mapping = SEARCH_FIELD_MAPPING | (request.field_mapping or {})
        return self._map_fields(merged, mapping)

    def build_publish_status_fields(self, record: dict[str, Any], request: XhsFeishuWriteRequest) -> dict[str, Any]:
        """Build Feishu publish-pool fields for one publish result."""
        merged = dict(record)
        merged.setdefault("job_id", request.job_id)
        merged.setdefault("account_id", request.account_id)
        merged.setdefault("provider_type", record.get("provider_type") or "kuaijingvs_yingdao_rpa")
        merged.setdefault("status", record.get("status") or "dry_run_planned")
        if "body_summary" not in merged and merged.get("body"):
            merged["body_summary"] = str(merged.get("body") or "")[:120]
        merged.setdefault("updated_at", self._utc_now())
        mapping = PUBLISH_FIELD_MAPPING | (request.field_mapping or {})
        return self._map_fields(merged, mapping)

    def build_feishu_write_plan(self, request: XhsFeishuWriteRequest) -> XhsFeishuWritePlan:
        """Build a Feishu write plan without executing network calls."""
        normalized = self._normalize_job_type(request.job_type)
        target = self.resolve_target_table(normalized, request)
        records = self.load_source_records(request)
        if request.operation == "update" and not request.feishu_record_id and not all(record.get("feishu_record_id") for record in records):
            raise WorkerError(FEISHU_RECORD_ID_REQUIRED, "Feishu update requires feishu_record_id")
        write_enabled = self.get_feishu_write_enabled()
        real_write_allowed = self.get_real_write_allowed(request)
        items: list[XhsFeishuWritePlanItem] = []
        for record in records:
            fields = (
                self.build_search_hotspot_fields(record, request)
                if normalized == "search"
                else self.build_publish_status_fields(record, request)
            )
            record_id = request.feishu_record_id or record.get("feishu_record_id")
            items.append(
                XhsFeishuWritePlanItem(
                    operation=request.operation,
                    record_id=record_id,
                    fields=fields,
                    write_allowed=real_write_allowed,
                    skip_reason="dry_run" if request.dry_run else (None if real_write_allowed else FEISHU_WRITE_DISABLED),
                )
            )
        return XhsFeishuWritePlan(
            job_id=request.job_id,
            job_type=normalized,
            operation=request.operation,
            dry_run=request.dry_run,
            target_table_kind=target["target_table_kind"],
            write_enabled=write_enabled,
            real_write_allowed=real_write_allowed,
            app_token_configured=target["app_token_configured"],
            table_id_configured=target["table_id_configured"],
            items=items,
            source_result_path=self._safe_path_value(request.source_result_path) if request.source_result_path else None,
            source_summary_path=self._safe_path_value(request.source_summary_path) if request.source_summary_path else None,
        )

    def build_feishu_payload(self, plan: XhsFeishuWritePlan) -> XhsFeishuWritePayload:
        """Build Feishu API-shaped payload without credentials."""
        records: list[dict[str, Any]] = []
        for item in plan.items:
            payload_item: dict[str, Any] = {"fields": item.fields}
            if item.operation == "update" and item.record_id:
                payload_item["record_id"] = item.record_id
            records.append(payload_item)
        return XhsFeishuWritePayload(
            job_id=plan.job_id,
            job_type=plan.job_type,
            operation=plan.operation,
            target_table_kind=plan.target_table_kind,
            records=records,
        )

    def execute_feishu_write(self, plan: XhsFeishuWritePlan, payload: XhsFeishuWritePayload, request: XhsFeishuWriteRequest) -> tuple[int, str | None]:
        """Execute real Feishu write only when explicitly allowed."""
        if request.dry_run or not plan.real_write_allowed:
            return 0, None
        self._validate_write_config(request)
        token = self._get_tenant_access_token()
        target = self.resolve_target_table(plan.job_type, request)
        table_id = target["table_id"]
        app_token = target["app_token"]
        first_record_id = None
        for record in payload.records:
            if plan.operation == "create":
                response = self._feishu_request(
                    "POST",
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                    {"Authorization": f"Bearer {token}"},
                    {"fields": record["fields"]},
                )
                first_record_id = first_record_id or self._extract_record_id(response)
            elif plan.operation == "update":
                record_id = record.get("record_id")
                if not record_id:
                    raise WorkerError(FEISHU_RECORD_ID_REQUIRED, "Feishu update requires record_id")
                self._feishu_request(
                    "PUT",
                    f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
                    {"Authorization": f"Bearer {token}"},
                    {"fields": record["fields"]},
                )
                first_record_id = first_record_id or str(record_id)
        return len(payload.records), first_record_id

    def readback_search(self, request: XhsFeishuReadbackRequest) -> XhsFeishuReadbackSummary:
        """Build or execute a controlled search readback check."""
        return self._run_readback(request.model_copy(update={"job_type": "search"}))

    def readback_publish(self, request: XhsFeishuReadbackRequest) -> XhsFeishuReadbackSummary:
        """Build or execute a controlled publish readback check."""
        return self._run_readback(request.model_copy(update={"job_type": "publish"}))

    def read_feishu_record(self, request: XhsFeishuReadbackRequest) -> dict[str, Any]:
        """Read one Feishu record. This never lists records or performs batch reads."""
        if not request.feishu_record_id:
            raise WorkerError(FEISHU_READBACK_RECORD_ID_REQUIRED, "Feishu readback requires feishu_record_id")
        token = self._get_tenant_access_token()
        target = self.resolve_target_table(request.job_type, self._readback_to_write_request(request))
        response = self._feishu_request(
            "GET",
            f"/open-apis/bitable/v1/apps/{target['app_token']}/tables/{target['table_id']}/records/{request.feishu_record_id}",
            {"Authorization": f"Bearer {token}"},
            {},
        )
        fields = self._extract_readback_fields(response)
        if not fields:
            raise WorkerError(FEISHU_READBACK_FAILED, "Feishu readback response did not include fields")
        return fields

    def build_expected_readback_fields(self, request: XhsFeishuReadbackRequest) -> dict[str, Any]:
        """Build expected readback fields from the same mapping used for writes."""
        write_request = self._readback_to_write_request(request)
        plan = self.build_feishu_write_plan(write_request)
        if len(plan.items) != 1:
            raise WorkerError(FEISHU_PAYLOAD_INVALID, "Feishu readback smoke supports exactly one record")
        return dict(plan.items[0].fields)

    def normalize_readback_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Normalize Feishu readback field values for stable comparisons."""
        normalized: dict[str, Any] = {}
        for key, value in fields.items():
            if isinstance(value, list):
                normalized[key] = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                normalized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            else:
                normalized[key] = value
        return normalized

    def compare_expected_vs_readback(self, expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
        """Compare expected and actual Feishu fields."""
        expected_norm = self.normalize_readback_fields(expected)
        actual_norm = self.normalize_readback_fields(actual)
        matched: list[str] = []
        missing: list[str] = []
        mismatched: list[str] = []
        for key, expected_value in expected_norm.items():
            if key not in actual_norm:
                missing.append(key)
            elif str(actual_norm[key]) == str(expected_value):
                matched.append(key)
            else:
                mismatched.append(key)
        extra = sorted(key for key in actual_norm.keys() if key not in expected_norm)
        return {
            "matched_fields": sorted(matched),
            "missing_fields": sorted(missing),
            "mismatched_fields": sorted(mismatched),
            "extra_fields": extra,
            "check_passed": not missing and not mismatched,
        }

    def write_readback_outputs(
        self,
        request: XhsFeishuReadbackRequest,
        expected: dict[str, Any],
        actual: dict[str, Any],
        check: XhsFeishuReadbackCheck,
        summary: XhsFeishuReadbackSummary,
    ) -> XhsFeishuReadbackSummary:
        """Write readback expected, actual, check, and summary JSON."""
        paths = self.get_readback_output_paths(request.job_id, request.job_type)
        self._write_json(Path(paths["expected_path"]), expected)
        if not request.dry_run:
            self._write_json(Path(paths["actual_path"]), actual)
        self._write_json(Path(paths["check_path"]), self._model_to_dict(check))
        self._write_json(Path(paths["summary_path"]), self._model_to_dict(summary))
        return summary

    def get_readback_output_paths(self, job_id: str, job_type: str) -> dict[str, str]:
        """Return local Feishu readback output paths."""
        normalized = self._normalize_job_type(job_type)
        output_dir = self.readback_output_root / normalized / job_id
        return {
            "output_dir": str(output_dir),
            "request_path": str(output_dir / "feishu_readback_request.json"),
            "expected_path": str(output_dir / "feishu_readback_expected.json"),
            "actual_path": str(output_dir / "feishu_readback_actual.json"),
            "check_path": str(output_dir / "feishu_readback_check.json"),
            "summary_path": str(output_dir / "feishu_readback_summary.json"),
        }

    def write_feishu_outputs(
        self,
        plan: XhsFeishuWritePlan,
        payload: XhsFeishuWritePayload,
        result: XhsFeishuWriteResult,
        summary: XhsFeishuWriteSummary,
    ) -> XhsFeishuWriteResult:
        """Write Feishu plan/payload/result/summary JSON."""
        self._write_json(Path(result.plan_path or ""), self._model_to_dict(plan))
        self._write_json(Path(result.payload_path or ""), self._model_to_dict(payload))
        self._write_json(Path(result.result_path or ""), self._model_to_dict(result))
        self._write_json(Path(result.summary_path or ""), self._model_to_dict(summary))
        return result

    def get_output_paths(self, job_id: str, job_type: str) -> dict[str, str]:
        """Return local Feishu write output paths."""
        normalized = self._normalize_job_type(job_type)
        output_dir = self.output_root / normalized / job_id
        return {
            "output_dir": str(output_dir),
            "plan_path": str(output_dir / "feishu_write_plan.json"),
            "payload_path": str(output_dir / "feishu_write_payload.json"),
            "result_path": str(output_dir / "feishu_write_result.json"),
            "summary_path": str(output_dir / "feishu_write_summary.json"),
        }

    def _run(self, request: XhsFeishuWriteRequest) -> XhsFeishuWriteResult:
        normalized = self._normalize_job_type(request.job_type)
        request = request.model_copy(update={"job_type": normalized})
        paths = self.get_output_paths(request.job_id, normalized)
        status = "success"
        error_code = None
        error_message = None
        sensitive_detected = False
        written_count = 0
        record_id = None
        plan = XhsFeishuWritePlan(
            job_id=request.job_id,
            job_type=normalized,
            operation=request.operation,
            target_table_kind="search_hotspot_pool" if normalized == "search" else "publish_status_pool",
        )
        payload = XhsFeishuWritePayload(
            job_id=request.job_id,
            job_type=normalized,
            operation=request.operation,
            target_table_kind=plan.target_table_kind,
        )
        scan = {"passed": True, "matches": []}
        try:
            plan = self.build_feishu_write_plan(request)
            payload = self.build_feishu_payload(plan)
            scan = self.scan_payload_for_sensitive_values(self._model_to_dict(payload))
            if not scan["passed"]:
                sensitive_detected = True
                raise WorkerError(FEISHU_SENSITIVE_VALUE_BLOCKED, f"Feishu payload contains sensitive content: {scan['matches']}")
            if not request.dry_run and not plan.real_write_allowed:
                raise WorkerError(FEISHU_WRITE_DISABLED, "real Feishu write is not explicitly enabled or configured")
            written_count, record_id = self.execute_feishu_write(plan, payload, request)
        except WorkerError as exc:
            status = "failed"
            error_code = exc.error_code
            error_message = exc.error_message
            if exc.error_code == FEISHU_SENSITIVE_VALUE_BLOCKED:
                sensitive_detected = True
            plan = plan.model_copy(update={"error_code": error_code, "error_message": error_message})
        planned_create_count = sum(1 for item in plan.items if item.operation == "create")
        planned_update_count = sum(1 for item in plan.items if item.operation == "update")
        skipped_count = max(len(plan.items) - written_count, 0)
        result = XhsFeishuWriteResult(
            job_id=request.job_id,
            job_type=normalized,
            account_id=request.account_id,
            status=status,
            operation=request.operation,
            dry_run=request.dry_run,
            write_enabled=plan.write_enabled,
            real_write_allowed=plan.real_write_allowed,
            target_table_kind=plan.target_table_kind,
            record_count=len(plan.items),
            planned_create_count=planned_create_count,
            planned_update_count=planned_update_count,
            written_count=written_count,
            skipped_count=skipped_count,
            record_id=record_id,
            plan_path=paths["plan_path"],
            payload_path=paths["payload_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            sensitive_payload_detected=sensitive_detected,
            error_code=error_code,
            error_message=error_message,
        )
        summary = XhsFeishuWriteSummary(
            job_id=request.job_id,
            job_type=normalized,
            operation=request.operation,
            dry_run=request.dry_run,
            write_enabled=plan.write_enabled,
            real_write_allowed=plan.real_write_allowed,
            target_table_kind=plan.target_table_kind,
            record_count=len(plan.items),
            planned_create_count=planned_create_count,
            planned_update_count=planned_update_count,
            written_count=written_count,
            skipped_count=skipped_count,
            record_id=record_id,
            plan_path=paths["plan_path"],
            payload_path=paths["payload_path"],
            result_path=paths["result_path"],
            summary_path=paths["summary_path"],
            payload_scan=scan,
            forbidden_actions=self._forbidden_actions(),
            created_at=self._utc_now(),
            error_code=error_code,
            error_message=error_message,
        )
        self.write_feishu_outputs(plan, payload, result, summary)
        return result

    def _run_readback(self, request: XhsFeishuReadbackRequest) -> XhsFeishuReadbackSummary:
        normalized = self._normalize_job_type(request.job_type)
        request = request.model_copy(update={"job_type": normalized})
        paths = self.get_readback_output_paths(request.job_id, normalized)
        expected: dict[str, Any] = {}
        actual: dict[str, Any] = {}
        real_allowed = False
        status_error_code = None
        status_error_message = None
        check_result = {
            "matched_fields": [],
            "missing_fields": [],
            "mismatched_fields": [],
            "extra_fields": [],
            "check_passed": False,
        }
        try:
            dry_run_planning = request.dry_run and bool(request.account_id) and bool(request.records)
            if request.operation == "readback" and not request.feishu_record_id and not dry_run_planning:
                raise WorkerError(FEISHU_READBACK_RECORD_ID_REQUIRED, "Feishu readback requires feishu_record_id")
            expected = self.build_expected_readback_fields(request)
            scan = self.scan_payload_for_sensitive_values(expected)
            if not scan["passed"]:
                raise WorkerError(FEISHU_SENSITIVE_VALUE_BLOCKED, f"Feishu readback expected fields contain sensitive content: {scan['matches']}")
            real_allowed = self.get_real_readback_allowed(request)
            if not request.dry_run and not real_allowed:
                raise WorkerError(FEISHU_READBACK_DISABLED, "real Feishu readback is not explicitly enabled or configured")
            if request.dry_run:
                if self._truthy(self._get("XHS_FEISHU_READBACK_REQUIRE_SMOKE_MARKER", "true")) and not self._contains_smoke_marker(expected):
                    raise WorkerError(FEISHU_READBACK_MARKER_REQUIRED, "Feishu readback expected fields do not contain XHS_SMOKE marker")
                check_result = {
                    "matched_fields": sorted(expected.keys()),
                    "missing_fields": [],
                    "mismatched_fields": [],
                    "extra_fields": [],
                    "check_passed": True,
                }
            elif real_allowed:
                actual = self.read_feishu_record(request)
                if self._truthy(self._get("XHS_FEISHU_READBACK_REQUIRE_SMOKE_MARKER", "true")) and not self._contains_smoke_marker(actual):
                    raise WorkerError(FEISHU_READBACK_MARKER_REQUIRED, "Feishu readback record does not contain XHS_SMOKE marker")
                check_result = self.compare_expected_vs_readback(expected, actual)
                check_result["check_passed"] = True
            else:
                check_result = {
                    "matched_fields": [],
                    "missing_fields": sorted(expected.keys()) if request.dry_run else [],
                    "mismatched_fields": [],
                    "extra_fields": [],
                    "check_passed": request.dry_run,
                }
        except WorkerError as exc:
            status_error_code = exc.error_code
            status_error_message = exc.error_message
        except Exception as exc:
            status_error_code = FEISHU_READBACK_FAILED
            status_error_message = f"Feishu readback failed: {exc}"
        check = XhsFeishuReadbackCheck(
            job_id=request.job_id,
            job_type=normalized,
            operation=request.operation,
            dry_run=request.dry_run,
            record_id=request.feishu_record_id,
            expected_fields=expected,
            actual_fields=actual,
            matched_fields=check_result["matched_fields"],
            missing_fields=check_result["missing_fields"],
            mismatched_fields=check_result["mismatched_fields"],
            extra_fields=check_result["extra_fields"],
            check_passed=check_result["check_passed"] and status_error_code is None,
            error_code=status_error_code,
            error_message=status_error_message,
        )
        summary = XhsFeishuReadbackSummary(
            job_id=request.job_id,
            job_type=normalized,
            status="success" if status_error_code is None else "failed",
            operation=request.operation,
            dry_run=request.dry_run,
            readback_enabled=self.get_feishu_readback_enabled(),
            real_readback_allowed=self.get_real_readback_allowed(request),
            record_id_present=bool(request.feishu_record_id),
            expected_field_count=len(expected),
            actual_field_count=len(actual),
            matched_field_count=len(check.matched_fields),
            mismatched_field_count=len(check.mismatched_fields),
            missing_field_count=len(check.missing_fields),
            extra_field_count=len(check.extra_fields),
            check_passed=check.check_passed,
            request_path=paths["request_path"],
            expected_path=paths["expected_path"],
            actual_path=None if request.dry_run else paths["actual_path"],
            check_path=paths["check_path"],
            summary_path=paths["summary_path"],
            created_at=self._utc_now(),
            error_code=status_error_code,
            error_message=status_error_message,
        )
        self._write_json(Path(paths["request_path"]), self._model_to_dict(request))
        self.write_readback_outputs(request, expected, actual, check, summary)
        return summary

    def _contains_smoke_marker(self, value: Any) -> bool:
        """Return whether a readback structure contains the smoke marker in any key or value."""
        return "XHS_SMOKE" in json.dumps(value, ensure_ascii=False)

    def _readback_to_write_request(self, request: XhsFeishuReadbackRequest) -> XhsFeishuWriteRequest:
        operation = "update" if request.operation == "update" else "create"
        return XhsFeishuWriteRequest(
            job_id=request.job_id,
            job_type=request.job_type,
            account_id=request.account_id,
            operation=operation,
            feishu_record_id=request.feishu_record_id,
            records=request.records,
            dry_run=request.dry_run,
            table_id=request.table_id,
            app_token=request.app_token,
            field_mapping=request.field_mapping,
        )

    def _extract_record_id(self, response: dict[str, Any]) -> str | None:
        candidates: list[Any] = [response.get("record_id"), response.get("id")]
        data = response.get("data")
        if isinstance(data, dict):
            candidates.extend([data.get("record_id"), data.get("id")])
            record = data.get("record")
            if isinstance(record, dict):
                candidates.extend([record.get("record_id"), record.get("id")])
        for candidate in candidates:
            if candidate:
                return str(candidate)
        return None

    def _extract_readback_fields(self, response: dict[str, Any]) -> dict[str, Any]:
        if isinstance(response.get("fields"), dict):
            return dict(response["fields"])
        data = response.get("data")
        if isinstance(data, dict):
            if isinstance(data.get("fields"), dict):
                return dict(data["fields"])
            record = data.get("record")
            if isinstance(record, dict) and isinstance(record.get("fields"), dict):
                return dict(record["fields"])
        return {}

    def _map_fields(self, record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for source_key, target_name in mapping.items():
            if source_key in record and record[source_key] is not None:
                value = record[source_key]
                if source_key.endswith("_path") or source_key == "evidence_json_path":
                    value = self._safe_path_value(value)
                fields[target_name] = self.sanitize_feishu_field_value(value)
        return fields

    def _validate_write_config(self, request: XhsFeishuWriteRequest) -> None:
        if not self.get_feishu_write_enabled():
            raise WorkerError(FEISHU_WRITE_DISABLED, "Feishu write adapter is disabled")
        if not self._truthy(self._get("XHS_ALLOW_REAL_FEISHU_WRITE", "false")):
            raise WorkerError(FEISHU_WRITE_DISABLED, "real Feishu writes are not explicitly allowed")
        if not self._feishu_configured(request):
            raise WorkerError(FEISHU_CONFIG_MISSING, "Feishu app id, app secret, app token, and table id are required for real write")

    def _feishu_configured(self, request: XhsFeishuWriteRequest) -> bool:
        target = self.resolve_target_table(request.job_type, request)
        return all(
            self._value_configured(value)
            for value in [
                self._get("XHS_FEISHU_APP_ID", self._get("FEISHU_APP_ID")),
                self._get("XHS_FEISHU_APP_SECRET", self._get("FEISHU_APP_SECRET")),
                target["app_token"],
                target["table_id"],
            ]
        )

    def _get_tenant_access_token(self) -> str:
        response = self._feishu_request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            {},
            {
                "app_id": self._get("XHS_FEISHU_APP_ID", self._get("FEISHU_APP_ID")),
                "app_secret": self._get("XHS_FEISHU_APP_SECRET", self._get("FEISHU_APP_SECRET")),
            },
        )
        token = response.get("tenant_access_token")
        if not token:
            raise WorkerError(FEISHU_WRITE_FAILED, "Feishu token response did not include tenant_access_token")
        return str(token)

    def _feishu_request(self, method: str, path: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        if self.http_client:
            return self.http_client(method, path, headers, body)
        base_url = (self._get("XHS_FEISHU_API_BASE_URL", "https://open.feishu.cn") or "").rstrip("/")
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib_request.Request(
            f"{base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json; charset=utf-8", **headers},
        )
        try:
            with urllib_request.urlopen(request, timeout=float(self._get("XHS_FEISHU_READ_TIMEOUT_SECONDS", "30") or "30")) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise WorkerError(FEISHU_WRITE_FAILED, f"Feishu write failed: {exc}") from exc

    def _forbidden_actions(self) -> dict[str, bool]:
        return {
            "real_minio_upload": True,
            "real_postgres_write": True,
            "external_n8n_call": True,
            "external_openclaw_call": True,
            "yingdao_openapi": True,
            "open_shop": True,
            "open_xhs": True,
            "open_external_webpage": True,
            "real_search": True,
            "real_publish": True,
        }

    def _safe_path_value(self, value: Any) -> str:
        text = str(value or "")
        path = Path(text)
        if not text:
            return text
        if path.is_absolute():
            try:
                return str(path.resolve().relative_to(self.worker_root.resolve())).replace("\\", "/")
            except Exception:
                return path.name
        return text.replace("\\", "/")

    def _looks_like_absolute_path(self, value: str) -> bool:
        return bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("/") or value.startswith("\\\\")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def _resolve_worker_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.worker_root / path

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "search"
        if normalized in {"publish", "xhs_publish"}:
            return "publish"
        raise WorkerError(FEISHU_PAYLOAD_INVALID, f"unsupported Feishu write job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _get(self, name: str, default: str | None = None) -> str | None:
        source = self.env if self.env is not None else os.environ
        value = source.get(name, default)
        return str(value).strip() if value is not None else None

    def _truthy(self, value: str | bool | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _value_configured(self, value: str | None) -> bool:
        normalized = str(value or "").strip()
        return normalized.lower() not in {"", "change_me", "changeme", "none", "null"}

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
