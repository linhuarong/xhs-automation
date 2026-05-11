import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    YingdaoExpectedActions,
    YingdaoFormAction,
    YingdaoFormFieldSpec,
    YingdaoFormFillTrace,
    YingdaoFormSimulatorInput,
    YingdaoFormSimulatorPrepareResult,
    YingdaoFormSimulatorResult,
    YingdaoFormSimulatorRuntime,
    YingdaoFormSimulatorSummary,
    YingdaoFormSimulatorVerifyResult,
    YingdaoFormSpec,
)
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import (
    XHS_YINGDAO_FORM_SIMULATOR_ERROR,
    XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION,
    XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING,
    XHS_YINGDAO_FORM_SIMULATOR_RESULT_INVALID,
    XHS_YINGDAO_FORM_SIMULATOR_RESULT_NOT_FOUND,
    XHS_YINGDAO_FORM_SIMULATOR_TRACE_INVALID,
    XHS_YINGDAO_FORM_SIMULATOR_TRACE_NOT_FOUND,
    XHS_YINGDAO_FORM_SIMULATOR_UNEXPECTED_ACTION,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class YingdaoFormFillSimulatorService:
    """Browserless local JSON form-fill simulator for Yingdao mapping tests."""

    def __init__(
        self,
        handoff_service: YingdaoLocalHandoffService | None = None,
        queue_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create the simulator service without starting browsers or RPA."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.handoff_service = handoff_service or YingdaoLocalHandoffService(
            queue_root=queue_root,
            worker_root=self.worker_root,
        )
        self.queue_root = self.handoff_service.queue_root

    def prepare_search_simulator(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> YingdaoFormSimulatorPrepareResult:
        """Prepare a search simulator package from a local active job."""
        handoff = self.handoff_service.prepare_search_handoff(
            {
                "job_id": job_id,
                "account_id": account_id,
                "provider_type": "yingdao_local_file_trigger",
                "keyword": keyword,
                "limit": limit,
                "capture_screenshot": True,
            }
        )
        payload = {
            "keyword": keyword,
            "limit": limit,
            "capture_screenshot": True,
        }
        return self._prepare_package(
            job_type="xhs_search",
            job_id=job_id,
            account_id=account_id,
            provider_type="yingdao_local_file_trigger",
            source_active_job_path=handoff.active_job_path,
            payload=payload,
        )

    def prepare_publish_simulator(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> YingdaoFormSimulatorPrepareResult:
        """Prepare a publish simulator package from a local active job."""
        handoff = self.handoff_service.prepare_publish_handoff(
            {
                "job_id": job_id,
                "account_id": account_id,
                "provider_type": "yingdao_local_file_trigger",
                "title": title,
                "body": body,
                "tags": tags,
                "image_paths": image_paths,
                "publish_mode": publish_mode,
            }
        )
        payload = {
            "title": title,
            "body": body,
            "tags": tags,
            "tags_text": ",".join(tags),
            "image_paths": image_paths,
            "publish_mode": publish_mode,
        }
        return self._prepare_package(
            job_type="xhs_publish",
            job_id=job_id,
            account_id=account_id,
            provider_type="yingdao_local_file_trigger",
            source_active_job_path=handoff.active_job_path,
            payload=payload,
        )

    def build_search_form_spec(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build fake search form fields."""
        return self._model_to_dict(
            YingdaoFormSpec(
                job_type="xhs_search",
                form_name="fake_xhs_search_form",
                fields=[
                    YingdaoFormFieldSpec(
                        field_key="keyword_input",
                        label="关键词",
                        type="text",
                        required=True,
                        source_path="payload.keyword",
                    ),
                    YingdaoFormFieldSpec(
                        field_key="limit_input",
                        label="结果数量",
                        type="number",
                        required=True,
                        source_path="payload.limit",
                    ),
                    YingdaoFormFieldSpec(
                        field_key="capture_screenshot_checkbox",
                        label="是否截图",
                        type="boolean",
                        required=False,
                        source_path="payload.capture_screenshot",
                    ),
                ],
            )
        )

    def build_publish_form_spec(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build fake publish form fields."""
        return self._model_to_dict(
            YingdaoFormSpec(
                job_type="xhs_publish",
                form_name="fake_xhs_publish_form",
                fields=[
                    YingdaoFormFieldSpec(
                        field_key="title_input",
                        label="标题",
                        type="text",
                        required=True,
                        source_path="payload.title",
                    ),
                    YingdaoFormFieldSpec(
                        field_key="body_textarea",
                        label="正文",
                        type="textarea",
                        required=True,
                        source_path="payload.body",
                    ),
                    YingdaoFormFieldSpec(
                        field_key="tags_input",
                        label="标签",
                        type="text",
                        required=False,
                        source_path="payload.tags_text",
                    ),
                    YingdaoFormFieldSpec(
                        field_key="image_paths_input",
                        label="图片路径",
                        type="json_array",
                        required=True,
                        source_path="payload.image_paths",
                    ),
                    YingdaoFormFieldSpec(
                        field_key="publish_mode_select",
                        label="发布模式",
                        type="select",
                        required=True,
                        source_path="payload.publish_mode",
                    ),
                ],
            )
        )

    def build_expected_actions(self, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Build the expected action sequence."""
        normalized = self._normalize_job_type(job_type)
        if normalized == "xhs_search":
            actions = [
                YingdaoFormAction(step=1, action="fill", field_key="keyword_input", value=payload["keyword"]),
                YingdaoFormAction(step=2, action="fill", field_key="limit_input", value=payload["limit"]),
                YingdaoFormAction(
                    step=3,
                    action="set",
                    field_key="capture_screenshot_checkbox",
                    value=payload.get("capture_screenshot", True),
                ),
            ]
            return self._model_to_dict(
                YingdaoExpectedActions(job_type="xhs_search", job_id=str(payload["job_id"]), actions=actions)
            )
        actions = [
            YingdaoFormAction(step=1, action="fill", field_key="title_input", value=payload["title"]),
            YingdaoFormAction(step=2, action="fill", field_key="body_textarea", value=payload["body"]),
            YingdaoFormAction(step=3, action="fill", field_key="tags_input", value=payload.get("tags_text", "")),
            YingdaoFormAction(step=4, action="set", field_key="image_paths_input", value=payload.get("image_paths", [])),
            YingdaoFormAction(step=5, action="set", field_key="publish_mode_select", value=payload.get("publish_mode")),
        ]
        return self._model_to_dict(
            YingdaoExpectedActions(
                job_type="xhs_publish",
                job_id=str(payload["job_id"]),
                actions=actions,
                forbidden_final_action="click_publish",
            )
        )

    def write_simulator_package(
        self,
        job_type: str,
        job_id: str,
        simulator_input: dict[str, Any],
        form_spec: dict[str, Any],
        expected_actions: dict[str, Any],
    ) -> dict[str, str]:
        """Write the simulator input package files."""
        paths = self.get_simulator_paths(job_type, job_id)
        return {
            "simulator_input_path": self._write_json(Path(paths["simulator_input_path"]), simulator_input),
            "form_spec_path": self._write_json(Path(paths["form_spec_path"]), form_spec),
            "expected_actions_path": self._write_json(Path(paths["expected_actions_path"]), expected_actions),
        }

    def read_form_fill_trace(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read form_fill_trace.json."""
        path = Path(self.get_simulator_paths(job_type, job_id)["trace_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_TRACE_NOT_FOUND,
                f"form_fill_trace not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_FORM_SIMULATOR_TRACE_INVALID)

    def read_simulator_result(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read simulator_result.json."""
        path = Path(self.get_simulator_paths(job_type, job_id)["result_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_RESULT_NOT_FOUND,
                f"simulator_result not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_FORM_SIMULATOR_RESULT_INVALID)

    def validate_form_fill_trace(
        self,
        trace: dict[str, Any],
        expected_actions: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate form-fill trace against expected actions and safety flags."""
        if not isinstance(trace, dict):
            raise WorkerError(XHS_YINGDAO_FORM_SIMULATOR_TRACE_INVALID, "trace must be a JSON object")
        runtime = trace.get("runtime") or {}
        for flag in ("opened_browser", "opened_xhs", "called_external_api", "clicked_real_publish"):
            if runtime.get(flag) is True:
                raise WorkerError(
                    XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION,
                    f"form-fill trace has forbidden runtime flag {flag}=true",
                )
        actions = trace.get("actions") or []
        expected = expected_actions.get("actions") or []
        for action in actions:
            if action.get("action") == "click_publish":
                raise WorkerError(
                    XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION,
                    "form-fill trace contains forbidden action click_publish",
                )
        expected_keys = [(item.get("step"), item.get("action"), item.get("field_key"), item.get("value")) for item in expected]
        actual_keys = [(item.get("step"), item.get("action"), item.get("field_key"), item.get("value")) for item in actions]
        unexpected = [action for action in actions if (action.get("step"), action.get("action"), action.get("field_key"), action.get("value")) not in expected_keys]
        if unexpected:
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_UNEXPECTED_ACTION,
                f"form-fill trace contains unexpected actions: {unexpected}",
            )
        if actual_keys != expected_keys:
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING,
                "form-fill trace does not match all expected required actions",
            )
        return trace

    def validate_simulator_result(self, result: dict[str, Any], form_spec: dict[str, Any]) -> dict[str, Any]:
        """Validate simulator result summary."""
        if not isinstance(result, dict):
            raise WorkerError(XHS_YINGDAO_FORM_SIMULATOR_RESULT_INVALID, "simulator result must be a JSON object")
        if result.get("missing_required_fields"):
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING,
                f"simulator result missing required fields: {result.get('missing_required_fields')}",
            )
        if result.get("unexpected_actions"):
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_UNEXPECTED_ACTION,
                f"simulator result unexpected actions: {result.get('unexpected_actions')}",
            )
        if result.get("forbidden_actions_detected"):
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION,
                f"simulator result forbidden actions: {result.get('forbidden_actions_detected')}",
            )
        result_flags = result.get("result") or {}
        for flag in ("opened_browser", "opened_xhs", "real_action_executed"):
            if result_flags.get(flag) is True:
                raise WorkerError(
                    XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION,
                    f"simulator result has forbidden flag {flag}=true",
                )
        required_fields = [field["field_key"] for field in form_spec.get("fields", []) if field.get("required")]
        if int(result.get("filled_field_count", 0)) < len(required_fields):
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING,
                "simulator result filled_field_count is less than required field count",
            )
        return result

    def verify_simulator(self, job_type: str, job_id: str) -> YingdaoFormSimulatorVerifyResult:
        """Verify trace/result and write simulator_summary.json."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_simulator_paths(normalized, job_id)
        summary = YingdaoFormSimulatorSummary()
        trace = None
        result = None
        status = "verified"
        error_code = None
        error_message = None
        message = "Yingdao browserless form-fill simulator verified"
        expected_actions = self._read_json(Path(paths["expected_actions_path"]), XHS_YINGDAO_FORM_SIMULATOR_ERROR)
        form_spec = self._read_json(Path(paths["form_spec_path"]), XHS_YINGDAO_FORM_SIMULATOR_ERROR)
        try:
            trace = self.read_form_fill_trace(normalized, job_id)
            summary.trace_exists = True
            self.validate_form_fill_trace(trace, expected_actions)
            summary.trace_valid = True
            runtime = trace.get("runtime") or {}
            summary.opened_browser = bool(runtime.get("opened_browser", False))
            summary.opened_xhs = bool(runtime.get("opened_xhs", False))
            summary.called_external_api = bool(runtime.get("called_external_api", False))
            summary.clicked_real_publish = bool(runtime.get("clicked_real_publish", False))
        except WorkerError as exc:
            if exc.error_code == XHS_YINGDAO_FORM_SIMULATOR_TRACE_NOT_FOUND:
                status = "waiting_simulator_result"
                message = "Waiting for form_fill_trace.json"
            else:
                status = "failed"
                message = "form_fill_trace.json invalid"
            error_code = exc.error_code
            error_message = exc.error_message
        if status != "failed":
            try:
                result = self.read_simulator_result(normalized, job_id)
                summary.result_exists = True
                self.validate_simulator_result(result, form_spec)
                summary.result_valid = True
                result_flags = result.get("result") or {}
                summary.real_action_executed = bool(result_flags.get("real_action_executed", False))
                summary.forbidden_actions_detected = result.get("forbidden_actions_detected") or []
                summary.unexpected_actions = result.get("unexpected_actions") or []
                summary.missing_required_fields = result.get("missing_required_fields") or []
            except WorkerError as exc:
                if exc.error_code == XHS_YINGDAO_FORM_SIMULATOR_RESULT_NOT_FOUND and status != "waiting_simulator_result":
                    status = "waiting_simulator_result"
                    message = "Waiting for simulator_result.json"
                elif exc.error_code != XHS_YINGDAO_FORM_SIMULATOR_RESULT_NOT_FOUND:
                    status = "failed"
                    message = "simulator_result.json invalid"
                if error_code is None or exc.error_code != XHS_YINGDAO_FORM_SIMULATOR_RESULT_NOT_FOUND:
                    error_code = exc.error_code
                    error_message = exc.error_message
        verify_result = YingdaoFormSimulatorVerifyResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            simulator_dir=paths["simulator_dir"],
            trace_path=paths["trace_path"],
            result_path=paths["result_path"],
            simulator_summary_path=paths["summary_path"],
            summary=summary,
            trace=trace,
            result=result,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        self.write_simulator_summary(self._model_to_dict(verify_result))
        return verify_result

    def write_mock_trace_and_result(self, job_type: str, job_id: str, status: str = "success") -> dict[str, str]:
        """Write mock trace/result for local tests only."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_simulator_paths(normalized, job_id)
        expected_actions = self._read_json(Path(paths["expected_actions_path"]), XHS_YINGDAO_FORM_SIMULATOR_ERROR)
        form_spec = self._read_json(Path(paths["form_spec_path"]), XHS_YINGDAO_FORM_SIMULATOR_ERROR)
        actions = []
        for action in expected_actions.get("actions", []):
            item = dict(action)
            item["success"] = True
            actions.append(item)
        trace = self._model_to_dict(
            YingdaoFormFillTrace(
                job_type=normalized,
                job_id=job_id,
                status=status,
                filled_at=self._utc_now(),
                runtime=YingdaoFormSimulatorRuntime(),
                actions=[YingdaoFormAction(**action) for action in actions],
            )
        )
        required_fields = [field["field_key"] for field in form_spec.get("fields", []) if field.get("required")]
        result = self._model_to_dict(
            YingdaoFormSimulatorResult(
                job_type=normalized,
                job_id=job_id,
                status=status,
                validated_at=self._utc_now(),
                field_count=len(form_spec.get("fields", [])),
                filled_field_count=len({action["field_key"] for action in actions}),
                missing_required_fields=[],
                unexpected_actions=[],
                forbidden_actions_detected=[],
                result={
                    "form_fill_completed": True,
                    "opened_browser": False,
                    "opened_xhs": False,
                    "real_action_executed": False,
                    "ready_for_future_rpa_ui_mapping": True,
                    "required_field_count": len(required_fields),
                },
            )
        )
        return {
            "trace_path": self._write_json(Path(paths["trace_path"]), trace),
            "result_path": self._write_json(Path(paths["result_path"]), result),
        }

    def write_simulator_summary(self, summary: dict[str, Any]) -> str:
        """Write simulator verification summary."""
        paths = self.get_simulator_paths(str(summary["job_type"]), str(summary["job_id"]))
        return self._write_json(Path(paths["summary_path"]), summary)

    def get_simulator_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return simulator package paths."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        simulator_dir = self.queue_root / "simulator" / category / job_id
        return {
            "simulator_dir": str(simulator_dir),
            "simulator_input_path": str(simulator_dir / "simulator_input.json"),
            "form_spec_path": str(simulator_dir / "form_spec.json"),
            "expected_actions_path": str(simulator_dir / "expected_actions.json"),
            "trace_path": str(simulator_dir / "form_fill_trace.json"),
            "result_path": str(simulator_dir / "simulator_result.json"),
            "summary_path": str(simulator_dir / "simulator_summary.json"),
        }

    def _prepare_package(
        self,
        job_type: str,
        job_id: str,
        account_id: str,
        provider_type: str,
        source_active_job_path: str,
        payload: dict[str, Any],
    ) -> YingdaoFormSimulatorPrepareResult:
        normalized = self._normalize_job_type(job_type)
        paths = self.get_simulator_paths(normalized, job_id)
        payload = dict(payload)
        payload["job_id"] = job_id
        form_spec = self.build_search_form_spec(payload) if normalized == "xhs_search" else self.build_publish_form_spec(payload)
        expected_actions = self.build_expected_actions(normalized, payload)
        simulator_input = self._model_to_dict(
            YingdaoFormSimulatorInput(
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                provider_type=provider_type,
                created_at=self._utc_now(),
                source_active_job_path=source_active_job_path,
                form_spec_path=paths["form_spec_path"],
                expected_actions_path=paths["expected_actions_path"],
                expected_trace_path=paths["trace_path"],
                expected_result_path=paths["result_path"],
                payload={key: value for key, value in payload.items() if key != "job_id"},
                forbidden_actions={
                    "open_browser": True,
                    "open_xhs": True,
                    "call_external_api": True,
                    "click_real_publish": True,
                },
            )
        )
        self.write_simulator_package(normalized, job_id, simulator_input, form_spec, expected_actions)
        return YingdaoFormSimulatorPrepareResult(
            job_id=job_id,
            job_type=normalized,
            status="waiting_simulator_result",
            simulator_dir=paths["simulator_dir"],
            simulator_input_path=paths["simulator_input_path"],
            form_spec_path=paths["form_spec_path"],
            expected_actions_path=paths["expected_actions_path"],
            expected_trace_path=paths["trace_path"],
            expected_result_path=paths["result_path"],
            message="Browserless form-fill simulator package prepared; no browser or webpage was opened.",
        )

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
            raise WorkerError(
                XHS_YINGDAO_FORM_SIMULATOR_ERROR,
                f"failed to write form-fill simulator JSON: {path}: {exc}",
            ) from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_YINGDAO_FORM_SIMULATOR_ERROR, f"unsupported simulator job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
