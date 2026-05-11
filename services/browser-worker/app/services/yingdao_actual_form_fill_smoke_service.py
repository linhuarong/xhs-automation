import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    YingdaoActualButtonAction,
    YingdaoActualFilledField,
    YingdaoActualFormFillInput,
    YingdaoActualFormFillPrepareResult,
    YingdaoActualFormFillResult,
    YingdaoActualFormFillRunbook,
    YingdaoActualFormFillRunbookStep,
    YingdaoActualFormFillRuntime,
    YingdaoActualFormFillSummary,
    YingdaoActualFormFillTrace,
    YingdaoActualFormFillVerifyResult,
)
from app.services.yingdao_selector_mapping_service import YingdaoSelectorMappingService
from app.utils.errors import (
    XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR,
    XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
    XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_URL,
    XHS_YINGDAO_ACTUAL_FORM_FILL_REAL_ACTION_FORBIDDEN,
    XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING,
    XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_INVALID,
    XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_NOT_FOUND,
    XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_INVALID,
    XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_NOT_FOUND,
    XHS_YINGDAO_ACTUAL_FORM_FILL_VALUE_MISMATCH,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class YingdaoActualFormFillSmokeService:
    """Prepare and verify actual desktop fill smoke against local HTML only."""

    def __init__(
        self,
        selector_mapping_service: YingdaoSelectorMappingService | None = None,
        queue_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create the service without calling Yingdao, browser, or network."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.selector_mapping_service = selector_mapping_service or YingdaoSelectorMappingService(
            queue_root=queue_root,
            worker_root=self.worker_root,
        )
        self.queue_root = self.selector_mapping_service.queue_root

    def prepare_search_actual_fill(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> YingdaoActualFormFillPrepareResult:
        """Prepare search local HTML actual form-fill smoke package."""
        payload = {"account_id": account_id, "keyword": keyword, "limit": limit}
        bundle = self.ensure_html_sandbox_and_mapping("xhs_search", job_id, payload)
        return self._prepare_actual_fill("xhs_search", job_id, account_id, bundle)

    def prepare_publish_actual_fill(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> YingdaoActualFormFillPrepareResult:
        """Prepare publish local HTML actual form-fill smoke package."""
        payload = {
            "account_id": account_id,
            "title": title,
            "body": body,
            "tags": tags,
            "image_paths": image_paths,
            "publish_mode": publish_mode,
        }
        bundle = self.ensure_html_sandbox_and_mapping("xhs_publish", job_id, payload)
        return self._prepare_actual_fill("xhs_publish", job_id, account_id, bundle)

    def ensure_html_sandbox_and_mapping(self, job_type: str, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Ensure the local HTML sandbox and selector mapping package exist."""
        normalized = self._normalize_job_type(job_type)
        if normalized == "xhs_search":
            mapping_result = self.selector_mapping_service.prepare_search_mapping(
                job_id,
                payload["account_id"],
                payload["keyword"],
                int(payload.get("limit", 20)),
            )
        else:
            mapping_result = self.selector_mapping_service.prepare_publish_mapping(
                job_id,
                payload["account_id"],
                payload["title"],
                payload["body"],
                payload.get("tags", []),
                payload.get("image_paths", []),
                payload.get("publish_mode", "manual_review"),
            )
        mapping_paths = self.selector_mapping_service.get_mapping_paths(normalized, job_id)
        mapping_input = self._read_json(Path(mapping_paths["input_path"]), XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR)
        selector_mapping = self._read_json(Path(mapping_paths["mapping_path"]), XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR)
        action_sequence = self._read_json(Path(mapping_paths["action_sequence_path"]), XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR)
        return {
            "mapping_result": mapping_result,
            "mapping_input": mapping_input,
            "selector_mapping": selector_mapping,
            "action_sequence": action_sequence,
        }

    def build_actual_form_fill_input(
        self,
        job_type: str,
        job_id: str,
        sandbox: dict[str, Any],
        mapping: dict[str, Any],
    ) -> dict[str, Any]:
        """Build actual form-fill input JSON."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_actual_paths(normalized, job_id)
        html_path = str(sandbox["html_path"])
        html_uri = Path(html_path).resolve().as_uri()
        input_json = YingdaoActualFormFillInput(
            job_type=normalized,
            job_id=job_id,
            account_id=str(sandbox["account_id"]),
            created_at=self._utc_now(),
            html_path=html_path,
            html_uri=html_uri,
            selector_mapping_path=str(mapping["selector_mapping_path"]),
            action_sequence_path=str(mapping["action_sequence_path"]),
            expected_trace_path=paths["trace_path"],
            expected_result_path=paths["result_path"],
            allowed_target={
                "local_html_only": True,
                "html_uri_must_start_with": "file://",
                "must_contain_local_queue_path": True,
            },
            forbidden={
                "external_network": True,
                "xiaohongshu_url": True,
                "real_publish": True,
                "real_search": True,
                "yingdao_openapi": True,
            },
        )
        return self._model_to_dict(input_json)

    def build_actual_form_fill_runbook(
        self,
        job_type: str,
        job_id: str,
        action_sequence: dict[str, Any],
        html_uri: str | None = None,
    ) -> dict[str, Any]:
        """Build desktop runbook for local HTML form filling."""
        normalized = self._normalize_job_type(job_type)
        steps = [
            YingdaoActualFormFillRunbookStep(
                step=1,
                action="open_local_html",
                target="html_uri",
                value=html_uri,
                safety="local_file_only",
            )
        ]
        for action in action_sequence.get("actions", []):
            action_type = action.get("action_type")
            if action_type == "click":
                selector = str(action.get("selector", ""))
                allowed_selector = "#simulate_search_button" if normalized == "xhs_search" else "#simulate_prepare_publish_button"
                if selector != allowed_selector:
                    raise WorkerError(
                        XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
                        f"actual form-fill only allows local simulate button: {selector}",
                    )
                steps.append(
                    YingdaoActualFormFillRunbookStep(
                        step=len(steps) + 1,
                        action="click",
                        field_key=action.get("field_key"),
                        selector=selector,
                        value=None,
                        safety="local_simulate_button_only",
                        required=False,
                    )
                )
            else:
                steps.append(
                    YingdaoActualFormFillRunbookStep(
                        step=len(steps) + 1,
                        action=action_type or "fill",
                        field_key=action.get("field_key"),
                        selector=action.get("selector"),
                        value=action.get("value"),
                        clear_before_fill=action.get("clear_before_fill"),
                        required=bool(action.get("required", True)),
                    )
                )
        steps.append(
            YingdaoActualFormFillRunbookStep(
                step=len(steps) + 1,
                action="write_trace_json",
                target="actual_form_fill_trace.json",
            )
        )
        steps.append(
            YingdaoActualFormFillRunbookStep(
                step=len(steps) + 1,
                action="write_result_json",
                target="actual_form_fill_result.json",
            )
        )
        runbook = YingdaoActualFormFillRunbook(
            job_type=normalized,
            job_id=job_id,
            steps=steps,
            forbidden_steps=[
                "xhs_site_opening",
                "external_site_opening",
                "real_publish_action",
                "call_yingdao_openapi",
                "call_kuaijingvs_open_shop",
            ],
        )
        return self._model_to_dict(runbook)

    def write_actual_form_fill_package(
        self,
        job_type: str,
        job_id: str,
        input_json: dict[str, Any],
        runbook_json: dict[str, Any],
    ) -> dict[str, str]:
        """Write actual form-fill input and runbook files."""
        paths = self.get_actual_paths(job_type, job_id)
        return {
            "actual_form_fill_input_path": self._write_json(Path(paths["input_path"]), input_json),
            "actual_form_fill_runbook_path": self._write_json(Path(paths["runbook_path"]), runbook_json),
        }

    def read_actual_form_fill_trace(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read actual_form_fill_trace.json."""
        path = Path(self.get_actual_paths(job_type, job_id)["trace_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_NOT_FOUND,
                f"actual form-fill trace not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_INVALID)

    def read_actual_form_fill_result(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read actual_form_fill_result.json."""
        path = Path(self.get_actual_paths(job_type, job_id)["result_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_NOT_FOUND,
                f"actual form-fill result not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_INVALID)

    def validate_actual_form_fill_trace(self, trace: dict[str, Any], runbook: dict[str, Any]) -> dict[str, Any]:
        """Validate actual local form-fill trace safety and values."""
        if not isinstance(trace, dict):
            raise WorkerError(XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_INVALID, "trace must be a JSON object")
        runtime = trace.get("runtime") or {}
        for flag in ("opened_external_url", "opened_xhs", "called_external_api", "clicked_real_publish"):
            if runtime.get(flag) is True:
                raise WorkerError(
                    XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
                    f"actual form-fill trace has forbidden runtime flag {flag}=true",
                )
        target = trace.get("target") or {}
        html_uri = str(target.get("html_uri") or "")
        if html_uri and (not html_uri.startswith("file://") or "xiaohongshu.com" in html_uri.lower()):
            raise WorkerError(XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_URL, "trace target is not a safe local file URI")
        if trace.get("forbidden_actions_detected"):
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
                f"actual form-fill trace detected forbidden actions: {trace.get('forbidden_actions_detected')}",
            )
        self._validate_button_actions(trace, runbook)
        missing, mismatches = self._compare_required_fields(trace.get("filled_fields") or [], runbook)
        if missing:
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING,
                f"actual form-fill trace missing required fields: {missing}",
            )
        if mismatches:
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_VALUE_MISMATCH,
                f"actual form-fill trace value mismatches: {mismatches}",
            )
        return trace

    def validate_actual_form_fill_result(self, result: dict[str, Any], runbook: dict[str, Any]) -> dict[str, Any]:
        """Validate actual local form-fill result safety and coverage."""
        if not isinstance(result, dict):
            raise WorkerError(XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_INVALID, "result must be a JSON object")
        if result.get("forbidden_actions_detected"):
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
                f"actual form-fill result detected forbidden actions: {result.get('forbidden_actions_detected')}",
            )
        flags = result.get("result") or {}
        if flags.get("external_url_opened") or flags.get("xhs_opened") or flags.get("clicked_real_publish"):
            raise WorkerError(XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION, "actual form-fill result reports forbidden action")
        if flags.get("real_search_executed") or flags.get("real_publish_executed"):
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_REAL_ACTION_FORBIDDEN,
                "actual form-fill result reports real search or publish",
            )
        missing = result.get("missing_required_fields") or []
        mismatches = result.get("value_mismatches") or []
        if missing:
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING,
                f"actual form-fill result missing required fields: {missing}",
            )
        if mismatches:
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_VALUE_MISMATCH,
                f"actual form-fill result value mismatches: {mismatches}",
            )
        required_count = len(self._required_steps(runbook))
        if int(result.get("filled_required_field_count", 0)) < required_count:
            raise WorkerError(
                XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING,
                "actual form-fill result did not fill all required fields",
            )
        return result

    def verify_actual_form_fill(self, job_type: str, job_id: str) -> YingdaoActualFormFillVerifyResult:
        """Verify actual form-fill trace/result and write summary."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_actual_paths(normalized, job_id)
        runbook = self._read_json(Path(paths["runbook_path"]), XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR)
        summary = YingdaoActualFormFillSummary()
        trace = None
        result = None
        status = "verified"
        message = "Yingdao actual local form-fill smoke verified"
        error_code = None
        error_message = None
        try:
            trace = self.read_actual_form_fill_trace(normalized, job_id)
            summary.trace_exists = True
            self.validate_actual_form_fill_trace(trace, runbook)
            summary.trace_valid = True
            runtime = trace.get("runtime") or {}
            summary.opened_local_html = bool(runtime.get("opened_local_html", False))
            summary.opened_external_url = bool(runtime.get("opened_external_url", False))
            summary.opened_xhs = bool(runtime.get("opened_xhs", False))
            summary.called_external_api = bool(runtime.get("called_external_api", False))
            summary.clicked_real_publish = bool(runtime.get("clicked_real_publish", False))

            result = self.read_actual_form_fill_result(normalized, job_id)
            summary.result_exists = True
            self.validate_actual_form_fill_result(result, runbook)
            summary.result_valid = True
            summary.missing_required_fields = result.get("missing_required_fields") or []
            summary.value_mismatches = result.get("value_mismatches") or []
            summary.forbidden_actions_detected = result.get("forbidden_actions_detected") or []
            flags = result.get("result") or {}
            summary.real_action_executed = bool(flags.get("real_search_executed") or flags.get("real_publish_executed"))
        except WorkerError as exc:
            if exc.error_code in {
                XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_NOT_FOUND,
                XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_NOT_FOUND,
            }:
                status = "waiting_actual_form_fill_result"
                message = "Waiting for actual_form_fill_trace.json and actual_form_fill_result.json"
            else:
                status = "failed"
                message = "actual local form-fill smoke output invalid"
            error_code = exc.error_code
            error_message = exc.error_message
        verify_result = YingdaoActualFormFillVerifyResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            actual_form_fill_dir=paths["actual_form_fill_dir"],
            trace_path=paths["trace_path"],
            result_path=paths["result_path"],
            actual_form_fill_summary_path=paths["summary_path"],
            summary=summary,
            trace=trace,
            result=result,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        self.write_actual_form_fill_summary(self._model_to_dict(verify_result))
        return verify_result

    def write_mock_trace_and_result(self, job_type: str, job_id: str, status: str = "success") -> dict[str, str]:
        """Write local mock trace and result for actual form-fill smoke."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_actual_paths(normalized, job_id)
        runbook = self._read_json(Path(paths["runbook_path"]), XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR)
        input_json = self._read_json(Path(paths["input_path"]), XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR)
        filled_fields = [
            YingdaoActualFilledField(
                step=int(step["step"]),
                field_key=str(step.get("field_key")),
                selector=str(step.get("selector")),
                value=step.get("value"),
                success=True,
            )
            for step in self._required_steps(runbook, include_optional=True)
        ]
        button_actions = [
            YingdaoActualButtonAction(
                step=int(step["step"]),
                element_id=str(step.get("field_key")),
                selector=str(step.get("selector")),
                action="click",
                success=True,
                local_simulate_button=True,
            )
            for step in runbook.get("steps", [])
            if step.get("action") == "click"
        ]
        trace = self._model_to_dict(
            YingdaoActualFormFillTrace(
                job_type=normalized,
                job_id=job_id,
                status=status,
                filled_at=self._utc_now(),
                runtime=YingdaoActualFormFillRuntime(),
                target={
                    "html_uri": input_json.get("html_uri"),
                    "local_html_confirmed": True,
                },
                filled_fields=filled_fields,
                button_actions=button_actions,
                forbidden_actions_detected=[],
            )
        )
        required_count = len(self._required_steps(runbook))
        result = self._model_to_dict(
            YingdaoActualFormFillResult(
                job_type=normalized,
                job_id=job_id,
                status=status,
                validated_at=self._utc_now(),
                required_field_count=required_count,
                filled_required_field_count=required_count,
                missing_required_fields=[],
                value_mismatches=[],
                forbidden_actions_detected=[],
                result={
                    "local_html_opened": True,
                    "external_url_opened": False,
                    "xhs_opened": False,
                    "real_search_executed": False,
                    "real_publish_executed": False,
                    "clicked_real_publish": False,
                    "actual_local_form_fill_completed": True,
                    "ready_for_future_non_sandbox_mapping": True,
                },
            )
        )
        return {
            "trace_path": self._write_json(Path(paths["trace_path"]), trace),
            "result_path": self._write_json(Path(paths["result_path"]), result),
        }

    def write_actual_form_fill_summary(self, summary: dict[str, Any]) -> str:
        """Write actual form-fill verification summary."""
        paths = self.get_actual_paths(str(summary["job_type"]), str(summary["job_id"]))
        return self._write_json(Path(paths["summary_path"]), summary)

    def get_actual_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return actual local form-fill paths."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        actual_dir = self.queue_root / "actual_form_fill" / category / job_id
        return {
            "actual_form_fill_dir": str(actual_dir),
            "input_path": str(actual_dir / "actual_form_fill_input.json"),
            "runbook_path": str(actual_dir / "actual_form_fill_runbook.json"),
            "trace_path": str(actual_dir / "actual_form_fill_trace.json"),
            "result_path": str(actual_dir / "actual_form_fill_result.json"),
            "summary_path": str(actual_dir / "actual_form_fill_summary.json"),
        }

    def _prepare_actual_fill(
        self,
        job_type: str,
        job_id: str,
        account_id: str,
        bundle: dict[str, Any],
    ) -> YingdaoActualFormFillPrepareResult:
        normalized = self._normalize_job_type(job_type)
        paths = self.get_actual_paths(normalized, job_id)
        mapping_result = bundle["mapping_result"]
        mapping_input = bundle["mapping_input"]
        mapping_paths = {
            "selector_mapping_path": mapping_result.selector_mapping_path,
            "action_sequence_path": mapping_result.action_sequence_path,
        }
        input_json = self.build_actual_form_fill_input(
            normalized,
            job_id,
            {
                "account_id": account_id,
                "html_path": mapping_input["html_path"],
            },
            mapping_paths,
        )
        runbook_json = self.build_actual_form_fill_runbook(
            normalized,
            job_id,
            bundle["action_sequence"],
            html_uri=input_json["html_uri"],
        )
        self.write_actual_form_fill_package(normalized, job_id, input_json, runbook_json)
        return YingdaoActualFormFillPrepareResult(
            job_id=job_id,
            job_type=normalized,
            status="waiting_actual_form_fill_result",
            actual_form_fill_dir=paths["actual_form_fill_dir"],
            html_path=input_json["html_path"],
            html_uri=input_json["html_uri"],
            actual_form_fill_input_path=paths["input_path"],
            actual_form_fill_runbook_path=paths["runbook_path"],
            expected_trace_path=paths["trace_path"],
            expected_result_path=paths["result_path"],
            message="Actual local HTML form-fill smoke prepared; only local sandbox HTML may be opened.",
        )

    def _validate_button_actions(self, trace: dict[str, Any], runbook: dict[str, Any]) -> None:
        normalized = self._normalize_job_type(runbook["job_type"])
        allowed_selector = "#simulate_search_button" if normalized == "xhs_search" else "#simulate_prepare_publish_button"
        allowed_id = allowed_selector.removeprefix("#")
        for action in trace.get("button_actions") or []:
            selector = str(action.get("selector") or "")
            element_id = str(action.get("element_id") or "")
            if selector != allowed_selector or element_id != allowed_id or action.get("local_simulate_button") is not True:
                raise WorkerError(
                    XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION,
                    f"actual form-fill button action is not local simulate button: {action}",
                )

    def _compare_required_fields(
        self,
        filled_fields: list[dict[str, Any]],
        runbook: dict[str, Any],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        filled_by_key = {item.get("field_key"): item for item in filled_fields}
        missing = []
        mismatches = []
        for step in self._required_steps(runbook):
            field_key = step.get("field_key")
            filled = filled_by_key.get(field_key)
            if not filled or filled.get("success") is not True:
                missing.append(str(field_key))
                continue
            if filled.get("selector") != step.get("selector") or filled.get("value") != step.get("value"):
                mismatches.append(
                    {
                        "field_key": field_key,
                        "expected": step.get("value"),
                        "actual": filled.get("value"),
                    }
                )
        return missing, mismatches

    def _required_steps(self, runbook: dict[str, Any], include_optional: bool = False) -> list[dict[str, Any]]:
        fill_actions = {"fill", "select", "set"}
        return [
            step
            for step in runbook.get("steps", [])
            if step.get("action") in fill_actions and (include_optional or step.get("required") is True)
        ]

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
            raise WorkerError(XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR, f"failed to write actual form-fill JSON: {path}: {exc}") from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_YINGDAO_ACTUAL_FORM_FILL_ERROR, f"unsupported actual form-fill job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
