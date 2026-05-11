import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    YingdaoHtmlExpectedDom,
    YingdaoHtmlExpectedDomElement,
    YingdaoHtmlSandboxManifest,
    YingdaoHtmlSandboxPrepareResult,
    YingdaoHtmlSandboxResult,
    YingdaoHtmlSandboxRuntime,
    YingdaoHtmlSandboxSummary,
    YingdaoHtmlSandboxTrace,
    YingdaoHtmlSandboxVerifyResult,
)
from app.services.yingdao_form_fill_simulator_service import YingdaoFormFillSimulatorService
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import (
    XHS_YINGDAO_HTML_SANDBOX_ERROR,
    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_TEXT,
    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_URL,
    XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING,
    XHS_YINGDAO_HTML_SANDBOX_RESULT_INVALID,
    XHS_YINGDAO_HTML_SANDBOX_RESULT_NOT_FOUND,
    XHS_YINGDAO_HTML_SANDBOX_TRACE_INVALID,
    XHS_YINGDAO_HTML_SANDBOX_TRACE_NOT_FOUND,
    XHS_YINGDAO_HTML_SANDBOX_VALUE_MISMATCH,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class YingdaoLocalHtmlSandboxService:
    """Local static HTML sandbox for Yingdao field-mapping tests."""

    def __init__(
        self,
        form_simulator_service: YingdaoFormFillSimulatorService | None = None,
        queue_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create the sandbox service without opening browsers or external pages."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.form_simulator_service = form_simulator_service or YingdaoFormFillSimulatorService(
            handoff_service=YingdaoLocalHandoffService(queue_root=queue_root, worker_root=self.worker_root),
            queue_root=queue_root,
            worker_root=self.worker_root,
        )
        self.queue_root = self.form_simulator_service.queue_root

    def prepare_search_sandbox(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> YingdaoHtmlSandboxPrepareResult:
        """Prepare a local static search sandbox from a browserless simulator package."""
        simulator = self.form_simulator_service.prepare_search_simulator(job_id, account_id, keyword, limit)
        payload = {
            "keyword": keyword,
            "limit": limit,
            "capture_screenshot": True,
            "account_id": account_id,
            "source_simulator_dir": simulator.simulator_dir,
        }
        return self._prepare_package("xhs_search", job_id, account_id, payload)

    def prepare_publish_sandbox(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> YingdaoHtmlSandboxPrepareResult:
        """Prepare a local static publish sandbox from a browserless simulator package."""
        simulator = self.form_simulator_service.prepare_publish_simulator(
            job_id=job_id,
            account_id=account_id,
            title=title,
            body=body,
            tags=tags,
            image_paths=image_paths,
            publish_mode=publish_mode,
        )
        payload = {
            "title": title,
            "body": body,
            "tags": tags,
            "tags_text": ",".join(tags),
            "image_paths": image_paths,
            "image_paths_text": "\n".join(image_paths),
            "publish_mode": publish_mode,
            "account_id": account_id,
            "source_simulator_dir": simulator.simulator_dir,
        }
        return self._prepare_package("xhs_publish", job_id, account_id, payload)

    def build_search_html(self, payload: dict[str, Any]) -> str:
        """Build a self-contained fake search form."""
        keyword = html.escape(str(payload.get("keyword", "")))
        limit = html.escape(str(payload.get("limit", 20)))
        checked = " checked" if payload.get("capture_screenshot", True) else ""
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Local XHS Search Sandbox</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 760px; margin: 32px auto; line-height: 1.5; }}
    label {{ display: block; margin: 14px 0; }}
    input, textarea, select, button {{ font: inherit; padding: 8px; width: 100%; box-sizing: border-box; }}
    input[type="checkbox"] {{ width: auto; }}
    button {{ margin-top: 12px; }}
    .warning {{ color: #8a4b00; background: #fff4d6; padding: 10px; }}
    #sandbox_result {{ margin-top: 18px; padding: 10px; border: 1px solid #ccc; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Local XHS Search Sandbox</h1>
  <p class="warning">This is a local fake sandbox. It does not open Xiaohongshu.</p>
  <form id="xhs-search-sandbox-form" action="">
    <label>Keyword
      <input id="keyword_input" name="keyword_input" type="text" value="{keyword}">
    </label>
    <label>Limit
      <input id="limit_input" name="limit_input" type="number" value="{limit}">
    </label>
    <label>
      <input id="capture_screenshot_checkbox" name="capture_screenshot_checkbox" type="checkbox"{checked}>
      Capture screenshot
    </label>
    <button id="simulate_search_button" type="button">Simulate Search</button>
  </form>
  <div id="sandbox_result" aria-live="polite"></div>
  <script>
    document.getElementById('simulate_search_button').addEventListener('click', function () {{
      var result = {{
        keyword_input: document.getElementById('keyword_input').value,
        limit_input: document.getElementById('limit_input').value,
        capture_screenshot_checkbox: document.getElementById('capture_screenshot_checkbox').checked
      }};
      document.getElementById('sandbox_result').textContent = JSON.stringify(result, null, 2);
    }});
  </script>
</body>
</html>
"""

    def build_publish_html(self, payload: dict[str, Any]) -> str:
        """Build a self-contained fake publish form."""
        title = html.escape(str(payload.get("title", "")))
        body = html.escape(str(payload.get("body", "")))
        tags_text = html.escape(str(payload.get("tags_text", "")))
        image_paths_text = html.escape(str(payload.get("image_paths_text", "")))
        publish_mode = html.escape(str(payload.get("publish_mode", "manual_review")))
        selected_manual = " selected" if publish_mode == "manual_review" else ""
        selected_draft = " selected" if publish_mode == "draft" else ""
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Local XHS Publish Sandbox</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 760px; margin: 32px auto; line-height: 1.5; }}
    label {{ display: block; margin: 14px 0; }}
    input, textarea, select, button {{ font: inherit; padding: 8px; width: 100%; box-sizing: border-box; }}
    input[type="checkbox"] {{ width: auto; }}
    textarea {{ min-height: 80px; }}
    button {{ margin-top: 12px; }}
    .warning {{ color: #8a4b00; background: #fff4d6; padding: 10px; }}
    #sandbox_result {{ margin-top: 18px; padding: 10px; border: 1px solid #ccc; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Local XHS Publish Sandbox</h1>
  <p class="warning">This is a local fake sandbox. It does not publish to Xiaohongshu.</p>
  <form id="xhs-publish-sandbox-form" action="">
    <label>Title
      <input id="title_input" name="title_input" type="text" value="{title}">
    </label>
    <label>Body
      <textarea id="body_textarea" name="body_textarea">{body}</textarea>
    </label>
    <label>Tags
      <input id="tags_input" name="tags_input" type="text" value="{tags_text}">
    </label>
    <label>Image paths
      <textarea id="image_paths_input" name="image_paths_input">{image_paths_text}</textarea>
    </label>
    <label>Mode
      <select id="publish_mode_select" name="publish_mode_select">
        <option value="manual_review"{selected_manual}>manual_review</option>
        <option value="draft"{selected_draft}>draft</option>
      </select>
    </label>
    <label>
      <input id="manual_review_checkbox" name="manual_review_checkbox" type="checkbox" checked>
      Manual review required
    </label>
    <button id="simulate_prepare_publish_button" type="button">Simulate Prepare</button>
  </form>
  <div id="sandbox_result" aria-live="polite"></div>
  <script>
    document.getElementById('simulate_prepare_publish_button').addEventListener('click', function () {{
      var result = {{
        title_input: document.getElementById('title_input').value,
        body_textarea: document.getElementById('body_textarea').value,
        tags_input: document.getElementById('tags_input').value,
        image_paths_input: document.getElementById('image_paths_input').value,
        publish_mode_select: document.getElementById('publish_mode_select').value,
        manual_review_checkbox: document.getElementById('manual_review_checkbox').checked
      }};
      document.getElementById('sandbox_result').textContent = JSON.stringify(result, null, 2);
    }});
  </script>
</body>
</html>
"""

    def build_expected_dom(self, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Build expected DOM contract for the fake local page."""
        normalized = self._normalize_job_type(job_type)
        if normalized == "xhs_search":
            elements = [
                YingdaoHtmlExpectedDomElement(id="keyword_input", type="input", expected_value=str(payload["keyword"])),
                YingdaoHtmlExpectedDomElement(id="limit_input", type="input", expected_value=str(payload["limit"])),
                YingdaoHtmlExpectedDomElement(
                    id="capture_screenshot_checkbox",
                    type="checkbox",
                    expected_checked=bool(payload.get("capture_screenshot", True)),
                ),
            ]
            forbidden = ["xiaohongshu.com", "小红书真实页面", "真实发布", "click_publish"]
        else:
            elements = [
                YingdaoHtmlExpectedDomElement(id="title_input", type="input", expected_value=str(payload["title"])),
                YingdaoHtmlExpectedDomElement(id="body_textarea", type="textarea", expected_value=str(payload["body"])),
                YingdaoHtmlExpectedDomElement(id="tags_input", type="input", expected_value=str(payload.get("tags_text", ""))),
                YingdaoHtmlExpectedDomElement(
                    id="image_paths_input",
                    type="textarea",
                    expected_value_contains=".local_assets",
                ),
                YingdaoHtmlExpectedDomElement(
                    id="publish_mode_select",
                    type="select",
                    expected_value=str(payload.get("publish_mode", "manual_review")),
                ),
            ]
            forbidden = ["xiaohongshu.com", "立即发布", "发布到小红书", "click_publish"]
        return self._model_to_dict(
            YingdaoHtmlExpectedDom(
                job_type=normalized,
                job_id=str(payload["job_id"]),
                required_elements=elements,
                forbidden_text=forbidden,
            )
        )

    def write_sandbox_package(
        self,
        job_type: str,
        job_id: str,
        html_content: str,
        manifest: dict[str, Any],
        expected_dom: dict[str, Any],
    ) -> dict[str, str]:
        """Write HTML sandbox package files."""
        paths = self.get_sandbox_paths(job_type, job_id)
        html_path = Path(paths["html_path"])
        html_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            html_path.write_text(html_content, encoding="utf-8")
            return {
                "html_path": str(html_path),
                "manifest_path": self._write_json(Path(paths["manifest_path"]), manifest),
                "expected_dom_path": self._write_json(Path(paths["expected_dom_path"]), expected_dom),
            }
        except OSError as exc:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_ERROR,
                f"failed to write local HTML sandbox package: {html_path}: {exc}",
            ) from exc

    def validate_html_safety(self, html_content: str) -> dict[str, Any]:
        """Validate generated HTML is local-only and contains no forbidden resources."""
        lowered = html_content.lower()
        forbidden_urls = [token for token in ("http://", "https://", "xiaohongshu.com") if token in lowered]
        if forbidden_urls:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_URL,
                f"HTML contains forbidden URL markers: {forbidden_urls}",
            )
        forbidden_resource_markers = ["<script src=", "<link ", "fetch(", "xmlhttprequest", "sendbeacon"]
        forbidden_resources = [token for token in forbidden_resource_markers if token in lowered]
        if forbidden_resources:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
                f"HTML contains forbidden resource or network markers: {forbidden_resources}",
            )
        forbidden_text = []
        for token in ("click_publish", "立即发布", "发布到小红书", "publish now"):
            if token.lower() in lowered:
                forbidden_text.append(token)
        if forbidden_text:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_TEXT,
                f"HTML contains forbidden text: {forbidden_text}",
            )
        return {"safe": True, "forbidden_urls": [], "forbidden_text": []}

    def read_sandbox_trace(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read sandbox_trace.json."""
        path = Path(self.get_sandbox_paths(job_type, job_id)["trace_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_TRACE_NOT_FOUND,
                f"sandbox_trace not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_HTML_SANDBOX_TRACE_INVALID)

    def read_sandbox_result(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read sandbox_result.json."""
        path = Path(self.get_sandbox_paths(job_type, job_id)["result_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_RESULT_NOT_FOUND,
                f"sandbox_result not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_HTML_SANDBOX_RESULT_INVALID)

    def validate_sandbox_trace(self, trace: dict[str, Any], expected_dom: dict[str, Any]) -> dict[str, Any]:
        """Validate trace runtime safety and required fields."""
        if not isinstance(trace, dict):
            raise WorkerError(XHS_YINGDAO_HTML_SANDBOX_TRACE_INVALID, "sandbox trace must be a JSON object")
        runtime = trace.get("runtime") or {}
        for flag in ("opened_external_url", "opened_xhs", "called_external_api", "clicked_real_publish"):
            if runtime.get(flag) is True:
                raise WorkerError(
                    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
                    f"sandbox trace has forbidden runtime flag {flag}=true",
                )
        for action in trace.get("button_actions") or []:
            if action.get("element_id") == "click_publish" or action.get("action") == "click_publish":
                raise WorkerError(
                    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
                    "sandbox trace contains forbidden publish action",
                )
        filled = {item.get("element_id"): item for item in trace.get("filled_fields") or []}
        missing = []
        mismatches = []
        for element in expected_dom.get("required_elements", []):
            element_id = element.get("id")
            item = filled.get(element_id)
            if item is None:
                missing.append(element_id)
                continue
            actual = item.get("value")
            if element.get("expected_value") is not None and str(actual) != str(element.get("expected_value")):
                mismatches.append({"id": element_id, "expected": element.get("expected_value"), "actual": actual})
            contains = element.get("expected_value_contains")
            if contains and contains not in str(actual):
                mismatches.append({"id": element_id, "expected_contains": contains, "actual": actual})
            if element.get("expected_checked") is not None and bool(actual) is not bool(element.get("expected_checked")):
                mismatches.append({"id": element_id, "expected_checked": element.get("expected_checked"), "actual": actual})
        if missing:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING,
                f"sandbox trace missing required elements: {missing}",
            )
        if mismatches:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_VALUE_MISMATCH,
                f"sandbox trace value mismatches: {mismatches}",
            )
        return trace

    def validate_sandbox_result(self, result: dict[str, Any], expected_dom: dict[str, Any]) -> dict[str, Any]:
        """Validate sandbox_result.json summary."""
        if not isinstance(result, dict):
            raise WorkerError(XHS_YINGDAO_HTML_SANDBOX_RESULT_INVALID, "sandbox result must be a JSON object")
        if result.get("missing_required_elements"):
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING,
                f"sandbox result missing required elements: {result.get('missing_required_elements')}",
            )
        if result.get("value_mismatches"):
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_VALUE_MISMATCH,
                f"sandbox result value mismatches: {result.get('value_mismatches')}",
            )
        if result.get("forbidden_actions_detected"):
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
                f"sandbox result forbidden actions: {result.get('forbidden_actions_detected')}",
            )
        if result.get("forbidden_text_detected"):
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_TEXT,
                f"sandbox result forbidden text: {result.get('forbidden_text_detected')}",
            )
        flags = result.get("result") or {}
        for flag in ("external_url_opened", "xhs_opened", "real_action_executed"):
            if flags.get(flag) is True:
                raise WorkerError(
                    XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION,
                    f"sandbox result has forbidden flag {flag}=true",
                )
        required_count = len(expected_dom.get("required_elements", []))
        if int(result.get("filled_element_count", 0)) < required_count:
            raise WorkerError(
                XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING,
                "sandbox result filled_element_count is less than required element count",
            )
        return result

    def verify_sandbox(self, job_type: str, job_id: str) -> YingdaoHtmlSandboxVerifyResult:
        """Verify trace/result and write sandbox_summary.json."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_sandbox_paths(normalized, job_id)
        expected_dom = self._read_json(Path(paths["expected_dom_path"]), XHS_YINGDAO_HTML_SANDBOX_ERROR)
        html_content = Path(paths["html_path"]).read_text(encoding="utf-8")
        self.validate_html_safety(html_content)
        summary = YingdaoHtmlSandboxSummary()
        trace = None
        result = None
        status = "verified"
        message = "Yingdao local HTML sandbox verified"
        error_code = None
        error_message = None
        try:
            trace = self.read_sandbox_trace(normalized, job_id)
            summary.trace_exists = True
            self.validate_sandbox_trace(trace, expected_dom)
            summary.trace_valid = True
            runtime = trace.get("runtime") or {}
            summary.opened_external_url = bool(runtime.get("opened_external_url", False))
            summary.opened_xhs = bool(runtime.get("opened_xhs", False))
            summary.called_external_api = bool(runtime.get("called_external_api", False))
            summary.clicked_real_publish = bool(runtime.get("clicked_real_publish", False))
        except WorkerError as exc:
            if exc.error_code == XHS_YINGDAO_HTML_SANDBOX_TRACE_NOT_FOUND:
                status = "waiting_sandbox_result"
                message = "Waiting for sandbox_trace.json"
            else:
                status = "failed"
                message = "sandbox_trace.json invalid"
            error_code = exc.error_code
            error_message = exc.error_message
        if status != "failed":
            try:
                result = self.read_sandbox_result(normalized, job_id)
                summary.result_exists = True
                self.validate_sandbox_result(result, expected_dom)
                summary.result_valid = True
                result_flags = result.get("result") or {}
                summary.real_action_executed = bool(result_flags.get("real_action_executed", False))
                summary.missing_required_elements = result.get("missing_required_elements") or []
                summary.value_mismatches = result.get("value_mismatches") or []
                summary.forbidden_actions_detected = result.get("forbidden_actions_detected") or []
                summary.forbidden_text_detected = result.get("forbidden_text_detected") or []
            except WorkerError as exc:
                if exc.error_code == XHS_YINGDAO_HTML_SANDBOX_RESULT_NOT_FOUND and status != "waiting_sandbox_result":
                    status = "waiting_sandbox_result"
                    message = "Waiting for sandbox_result.json"
                elif exc.error_code != XHS_YINGDAO_HTML_SANDBOX_RESULT_NOT_FOUND:
                    status = "failed"
                    message = "sandbox_result.json invalid"
                if error_code is None or exc.error_code != XHS_YINGDAO_HTML_SANDBOX_RESULT_NOT_FOUND:
                    error_code = exc.error_code
                    error_message = exc.error_message
        verify_result = YingdaoHtmlSandboxVerifyResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            sandbox_dir=paths["sandbox_dir"],
            trace_path=paths["trace_path"],
            result_path=paths["result_path"],
            sandbox_summary_path=paths["summary_path"],
            summary=summary,
            trace=trace,
            result=result,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        self.write_sandbox_summary(self._model_to_dict(verify_result))
        return verify_result

    def write_mock_trace_and_result(self, job_type: str, job_id: str, status: str = "success") -> dict[str, str]:
        """Write safe mock sandbox trace/result for local tests."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_sandbox_paths(normalized, job_id)
        expected_dom = self._read_json(Path(paths["expected_dom_path"]), XHS_YINGDAO_HTML_SANDBOX_ERROR)
        filled_fields = []
        for element in expected_dom.get("required_elements", []):
            value = element.get("expected_value")
            if value is None and element.get("expected_value_contains"):
                value = f"{element.get('expected_value_contains')}\\mock.png"
            if value is None and element.get("expected_checked") is not None:
                value = bool(element.get("expected_checked"))
            filled_fields.append({"element_id": element["id"], "value": value, "success": True})
        button_id = "simulate_search_button" if normalized == "xhs_search" else "simulate_prepare_publish_button"
        trace = self._model_to_dict(
            YingdaoHtmlSandboxTrace(
                job_type=normalized,
                job_id=job_id,
                status=status,
                filled_at=self._utc_now(),
                runtime=YingdaoHtmlSandboxRuntime(),
                filled_fields=filled_fields,
                button_actions=[{"element_id": button_id, "action": "click", "success": True}],
            )
        )
        result = self._model_to_dict(
            YingdaoHtmlSandboxResult(
                job_type=normalized,
                job_id=job_id,
                status=status,
                validated_at=self._utc_now(),
                required_element_count=len(expected_dom.get("required_elements", [])),
                filled_element_count=len(filled_fields),
                missing_required_elements=[],
                value_mismatches=[],
                forbidden_actions_detected=[],
                forbidden_text_detected=[],
                result={
                    "local_html_opened": True,
                    "external_url_opened": False,
                    "xhs_opened": False,
                    "real_action_executed": False,
                    "ready_for_future_rpa_ui_mapping": True,
                },
            )
        )
        return {
            "trace_path": self._write_json(Path(paths["trace_path"]), trace),
            "result_path": self._write_json(Path(paths["result_path"]), result),
        }

    def write_sandbox_summary(self, summary: dict[str, Any]) -> str:
        """Write sandbox verification summary."""
        paths = self.get_sandbox_paths(str(summary["job_type"]), str(summary["job_id"]))
        return self._write_json(Path(paths["summary_path"]), summary)

    def get_sandbox_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return all sandbox paths for a job."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        sandbox_dir = self.queue_root / "sandbox" / category / job_id
        html_name = "search_sandbox.html" if normalized == "xhs_search" else "publish_sandbox.html"
        html_path = sandbox_dir / html_name
        return {
            "sandbox_dir": str(sandbox_dir),
            "html_path": str(html_path),
            "html_uri": html_path.resolve().as_uri(),
            "manifest_path": str(sandbox_dir / "sandbox_manifest.json"),
            "expected_dom_path": str(sandbox_dir / "sandbox_expected_dom.json"),
            "trace_path": str(sandbox_dir / "sandbox_trace.json"),
            "result_path": str(sandbox_dir / "sandbox_result.json"),
            "summary_path": str(sandbox_dir / "sandbox_summary.json"),
        }

    def _prepare_package(
        self,
        job_type: str,
        job_id: str,
        account_id: str,
        payload: dict[str, Any],
    ) -> YingdaoHtmlSandboxPrepareResult:
        normalized = self._normalize_job_type(job_type)
        payload = dict(payload)
        payload["job_id"] = job_id
        paths = self.get_sandbox_paths(normalized, job_id)
        html_content = self.build_search_html(payload) if normalized == "xhs_search" else self.build_publish_html(payload)
        self.validate_html_safety(html_content)
        expected_dom = self.build_expected_dom(normalized, payload)
        manifest = self._model_to_dict(
            YingdaoHtmlSandboxManifest(
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                created_at=self._utc_now(),
                html_path=paths["html_path"],
                html_uri=paths["html_uri"],
                expected_dom_path=paths["expected_dom_path"],
                expected_trace_path=paths["trace_path"],
                expected_result_path=paths["result_path"],
                forbidden={
                    "external_network": True,
                    "xiaohongshu_url": True,
                    "real_publish": True,
                    "real_search": True,
                    "yingdao_openapi": True,
                },
            )
        )
        self.write_sandbox_package(normalized, job_id, html_content, manifest, expected_dom)
        return YingdaoHtmlSandboxPrepareResult(
            job_id=job_id,
            job_type=normalized,
            status="waiting_sandbox_result",
            sandbox_dir=paths["sandbox_dir"],
            html_path=paths["html_path"],
            html_uri=paths["html_uri"],
            manifest_path=paths["manifest_path"],
            expected_dom_path=paths["expected_dom_path"],
            expected_trace_path=paths["trace_path"],
            expected_result_path=paths["result_path"],
            message="Local static HTML sandbox prepared; no external page was opened.",
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
                XHS_YINGDAO_HTML_SANDBOX_ERROR,
                f"failed to write local HTML sandbox JSON: {path}: {exc}",
            ) from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_YINGDAO_HTML_SANDBOX_ERROR, f"unsupported HTML sandbox job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
