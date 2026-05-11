import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.schemas import (
    YingdaoActionSequence,
    YingdaoActionSequenceStep,
    YingdaoMappedElement,
    YingdaoSelectorMappingConfirmation,
    YingdaoSelectorMappingInput,
    YingdaoSelectorMappingPrepareResult,
    YingdaoSelectorMappingResult,
    YingdaoSelectorMappingRuntime,
    YingdaoSelectorMappingSummary,
    YingdaoSelectorMappingVerifyResult,
)
from app.services.yingdao_local_html_sandbox_service import YingdaoLocalHtmlSandboxService
from app.utils.errors import (
    XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_INVALID,
    XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_NOT_FOUND,
    XHS_YINGDAO_SELECTOR_MAPPING_ELEMENT_MISSING,
    XHS_YINGDAO_SELECTOR_MAPPING_ERROR,
    XHS_YINGDAO_SELECTOR_MAPPING_EXPECTED_DOM_NOT_FOUND,
    XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION,
    XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_TEXT,
    XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_URL,
    XHS_YINGDAO_SELECTOR_MAPPING_HTML_NOT_FOUND,
    XHS_YINGDAO_SELECTOR_MAPPING_SELECTOR_EMPTY,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class _SandboxElementParser(HTMLParser):
    """Tiny local HTML parser for fake sandbox form elements."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []
        self.labels_by_for: dict[str, str] = {}
        self._current_label: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "label":
            self._current_label = {"for": attr_map.get("for", ""), "text": ""}
        if tag in {"input", "textarea", "select", "button"}:
            element = {
                "tag": tag,
                "attrs": attr_map,
                "label": "",
            }
            if self._current_label is not None:
                element["label"] = self._current_label.get("text", "").strip()
            self.elements.append(element)

    def handle_data(self, data: str) -> None:
        if self._current_label is not None:
            self._current_label["text"] += data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._current_label is not None:
            label_for = self._current_label.get("for")
            if label_for:
                self.labels_by_for[label_for] = self._current_label.get("text", "").strip()
            self._current_label = None


class YingdaoSelectorMappingService:
    """Generate Yingdao selector mapping reports from local HTML sandbox pages."""

    def __init__(
        self,
        html_sandbox_service: YingdaoLocalHtmlSandboxService | None = None,
        queue_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create a selector mapping service without calling Yingdao or network."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.html_sandbox_service = html_sandbox_service or YingdaoLocalHtmlSandboxService(
            queue_root=queue_root,
            worker_root=self.worker_root,
        )
        self.queue_root = self.html_sandbox_service.queue_root

    def prepare_search_mapping(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> YingdaoSelectorMappingPrepareResult:
        """Prepare selector mapping for a local search HTML sandbox."""
        payload = {"account_id": account_id, "keyword": keyword, "limit": limit}
        return self._prepare_mapping("xhs_search", job_id, account_id, payload)

    def prepare_publish_mapping(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
        publish_mode: str = "manual_review",
    ) -> YingdaoSelectorMappingPrepareResult:
        """Prepare selector mapping for a local publish HTML sandbox."""
        payload = {
            "account_id": account_id,
            "title": title,
            "body": body,
            "tags": tags,
            "image_paths": image_paths,
            "publish_mode": publish_mode,
        }
        return self._prepare_mapping("xhs_publish", job_id, account_id, payload)

    def load_or_prepare_html_sandbox(self, job_type: str, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Prepare local HTML sandbox and return paths plus expected DOM."""
        normalized = self._normalize_job_type(job_type)
        if normalized == "xhs_search":
            sandbox = self.html_sandbox_service.prepare_search_sandbox(
                job_id,
                payload["account_id"],
                payload["keyword"],
                int(payload.get("limit", 20)),
            )
        else:
            sandbox = self.html_sandbox_service.prepare_publish_sandbox(
                job_id,
                payload["account_id"],
                payload["title"],
                payload["body"],
                payload.get("tags", []),
                payload.get("image_paths", []),
                payload.get("publish_mode", "manual_review"),
            )
        expected_dom = self._read_json(Path(sandbox.expected_dom_path), XHS_YINGDAO_SELECTOR_MAPPING_EXPECTED_DOM_NOT_FOUND)
        return {
            "sandbox": sandbox,
            "expected_dom": expected_dom,
            "html": Path(sandbox.html_path).read_text(encoding="utf-8"),
        }

    def parse_html_elements(self, html_content: str, expected_dom: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse only local sandbox HTML fields referenced by expected_dom."""
        self._validate_html_text_safety(html_content, expected_dom.get("forbidden_text", []))
        parser = _SandboxElementParser()
        parser.feed(html_content)
        by_id = {item.get("attrs", {}).get("id"): item for item in parser.elements if item.get("attrs", {}).get("id")}
        parsed = []
        for expected in expected_dom.get("required_elements", []):
            element_id = expected.get("id")
            raw = by_id.get(element_id)
            if raw is None:
                raise WorkerError(
                    XHS_YINGDAO_SELECTOR_MAPPING_ELEMENT_MISSING,
                    f"required sandbox element missing from HTML: {element_id}",
                )
            attrs = raw.get("attrs", {})
            parsed.append(
                {
                    "field_key": element_id,
                    "element_id": attrs.get("id") or element_id,
                    "element_name": attrs.get("name") or element_id,
                    "data_testid": attrs.get("data-testid") or element_id,
                    "tag": raw.get("tag"),
                    "type": attrs.get("type") or expected.get("type"),
                    "label": raw.get("label") or parser.labels_by_for.get(element_id) or element_id,
                    "required": True,
                    "expected_value": expected.get("expected_value"),
                    "expected_value_contains": expected.get("expected_value_contains"),
                    "expected_checked": expected.get("expected_checked"),
                }
            )
        return parsed

    def build_selector_candidates(self, element: dict[str, Any]) -> list[str]:
        """Build stable selector candidates for one local sandbox element."""
        tag = element.get("tag") or "*"
        element_id = element.get("element_id")
        element_name = element.get("element_name")
        data_testid = element.get("data_testid")
        candidates = []
        if element_id:
            candidates.extend([f"#{element_id}", f"{tag}#{element_id}"])
        if element_name:
            candidates.append(f"{tag}[name='{element_name}']")
        if data_testid:
            candidates.append(f"[data-testid='{data_testid}']")
        if element_id:
            candidates.append(f"//{tag}[@id='{element_id}']")
            candidates.append(f"html body #{element_id}")
        return list(dict.fromkeys(candidates))

    def choose_recommended_selector(self, candidates: list[str]) -> str:
        """Choose the recommended selector."""
        if not candidates:
            raise WorkerError(
                XHS_YINGDAO_SELECTOR_MAPPING_SELECTOR_EMPTY,
                "selector candidate list is empty",
            )
        return candidates[0]

    def build_selector_mapping(
        self,
        job_type: str,
        job_id: str,
        html_path: str,
        expected_dom: dict[str, Any],
    ) -> dict[str, Any]:
        """Build selector mapping JSON from local HTML and expected DOM."""
        html_file = Path(html_path)
        if not html_file.exists():
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_HTML_NOT_FOUND, f"HTML sandbox not found: {html_file}")
        html_content = html_file.read_text(encoding="utf-8")
        elements = []
        for parsed in self.parse_html_elements(html_content, expected_dom):
            candidates = self.build_selector_candidates(parsed)
            recommended = self.choose_recommended_selector(candidates)
            action_type = self._action_type_for(parsed)
            expected_value = self._expected_value_for(parsed)
            elements.append(
                YingdaoMappedElement(
                    field_key=parsed["field_key"],
                    label=parsed.get("label"),
                    element_id=parsed["element_id"],
                    element_name=parsed.get("element_name"),
                    tag=parsed["tag"],
                    type=parsed.get("type"),
                    required=True,
                    expected_value=expected_value,
                    recommended_selector=recommended,
                    selector_candidates=candidates,
                    yingdao_action={
                        "action_type": action_type,
                        "value": expected_value,
                        "clear_before_fill": action_type == "fill",
                    },
                    unique=True,
                    safe=True,
                )
            )
        mapping = YingdaoSelectorMappingResult(
            job_type=self._normalize_job_type(job_type),
            job_id=job_id,
            html_path=html_path,
            status="success",
            element_count=len(elements),
            elements=elements,
            forbidden_text_detected=[],
            forbidden_url_detected=False,
            real_publish_action_detected=False,
        )
        return self._model_to_dict(mapping)

    def build_action_sequence(self, selector_mapping: dict[str, Any]) -> dict[str, Any]:
        """Build Yingdao action sequence from selector mapping."""
        actions = []
        for index, element in enumerate(selector_mapping.get("elements", []), start=1):
            action = element.get("yingdao_action") or {}
            field_key = element["field_key"]
            notes = f"Use Yingdao input action with selector {element['recommended_selector']}."
            if field_key == "tags_input":
                notes = "Local fake tag input only; not a real Xiaohongshu tag control."
            if field_key == "image_paths_input":
                notes = "Fill local image path text only; no image upload."
            if field_key == "publish_mode_select":
                notes = "Select manual_review only; real publish is forbidden."
            actions.append(
                YingdaoActionSequenceStep(
                    step=index,
                    field_key=field_key,
                    selector=element["recommended_selector"],
                    action_type=action.get("action_type", "fill"),
                    value=action.get("value"),
                    clear_before_fill=action.get("clear_before_fill"),
                    required=bool(element.get("required", True)),
                    notes=notes,
                )
            )
        if selector_mapping["job_type"] == "xhs_publish":
            actions.append(
                YingdaoActionSequenceStep(
                    step=len(actions) + 1,
                    field_key="simulate_prepare_publish_button",
                    selector="#simulate_prepare_publish_button",
                    action_type="click",
                    value=None,
                    required=False,
                    notes="Click only the local simulation button; this is not a real publish button.",
                )
            )
        else:
            actions.append(
                YingdaoActionSequenceStep(
                    step=len(actions) + 1,
                    field_key="simulate_search_button",
                    selector="#simulate_search_button",
                    action_type="click",
                    value=None,
                    required=False,
                    notes="Click only the local simulation button; this is not a real search request.",
                )
            )
        sequence = YingdaoActionSequence(
            job_type=selector_mapping["job_type"],
            job_id=selector_mapping["job_id"],
            status="success",
            actions=actions,
            forbidden_actions=["click_real_publish", "open_xiaohongshu", "open_external_url"],
        )
        return self._model_to_dict(sequence)

    def build_markdown_report(self, selector_mapping: dict[str, Any], action_sequence: dict[str, Any]) -> str:
        """Build human-readable selector mapping report."""
        if "xiaohongshu.com" in json.dumps(selector_mapping, ensure_ascii=False).lower():
            raise WorkerError(
                XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_URL,
                "selector mapping contains xiaohongshu.com",
            )
        required_count = sum(1 for item in selector_mapping.get("elements", []) if item.get("required"))
        rows = []
        for action in action_sequence.get("actions", []):
            element = next((item for item in selector_mapping.get("elements", []) if item["field_key"] == action["field_key"]), {})
            rows.append(
                "| {step} | {field_key} | {label} | {tag} | `{selector}` | {action_type} | {value} | {required} | {unique} | {notes} |".format(
                    step=action["step"],
                    field_key=action["field_key"],
                    label=element.get("label", action["field_key"]),
                    tag=element.get("tag", "button"),
                    selector=action["selector"],
                    action_type=action["action_type"],
                    value=str(action.get("value", "")),
                    required=action.get("required"),
                    unique=element.get("unique", True),
                    notes=action.get("notes", ""),
                )
            )
        report = "\n".join(
            [
                "# Yingdao Local HTML Selector Mapping Report",
                "",
                "## Summary",
                f"- job_type: {selector_mapping['job_type']}",
                f"- job_id: {selector_mapping['job_id']}",
                f"- html_path: {selector_mapping['html_path']}",
                f"- element_count: {selector_mapping['element_count']}",
                f"- required_element_count: {required_count}",
                f"- selector_unique_count: {selector_mapping['element_count']}",
                "- forbidden_text_detected: []",
                "- forbidden_url_detected: false",
                "- real_action_detected: false",
                "",
                "## Safety Boundary",
                "- This report only maps local sandbox HTML.",
                "- It does not map Xiaohongshu real UI.",
                "- It does not open Xiaohongshu.",
                "- It does not publish.",
                "",
                "## Element Mapping Table",
                "| step | field_key | label | tag | recommended_selector | action_type | expected_value | required | unique | notes |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                *rows,
                "",
                "## Yingdao Desktop Action Guide",
                "1. Open the local HTML sandbox.",
                "2. Locate each selector listed in the table.",
                "3. Fill or set the local fake form value.",
                "4. Click only the local simulation button.",
                "5. Do not click any real publish action.",
                "6. Write selector_mapping_confirmation.json.",
                "",
                "## Forbidden Items Check",
                "- XHS domain marker: not found",
                "- external script/css: not found",
                "- real publish click marker: not found",
                "- real publish text: not found",
                "",
            ]
        )
        lowered = report.lower()
        if "xiaohongshu.com" in lowered:
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_URL, "report contains xiaohongshu.com")
        if selector_mapping["job_type"] == "xhs_publish" and "click_publish" in lowered:
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION, "publish report contains forbidden action")
        return report

    def write_mapping_package(
        self,
        job_type: str,
        job_id: str,
        mapping_input: dict[str, Any],
        selector_mapping: dict[str, Any],
        action_sequence: dict[str, Any],
        markdown_report: str,
    ) -> dict[str, str]:
        """Write selector mapping package files."""
        paths = self.get_mapping_paths(job_type, job_id)
        return {
            "selector_mapping_input_path": self._write_json(Path(paths["input_path"]), mapping_input),
            "selector_mapping_path": self._write_json(Path(paths["mapping_path"]), selector_mapping),
            "action_sequence_path": self._write_json(Path(paths["action_sequence_path"]), action_sequence),
            "mapping_report_path": self._write_text(Path(paths["report_path"]), markdown_report),
        }

    def read_mapping_confirmation(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read selector_mapping_confirmation.json."""
        path = Path(self.get_mapping_paths(job_type, job_id)["confirmation_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_NOT_FOUND,
                f"selector mapping confirmation not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_INVALID)

    def validate_mapping_confirmation(
        self,
        confirmation: dict[str, Any],
        selector_mapping: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate selector confirmation safety and coverage."""
        if not isinstance(confirmation, dict):
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_INVALID, "confirmation must be a JSON object")
        runtime = confirmation.get("runtime") or {}
        for flag in ("opened_external_url", "opened_xhs", "called_external_api", "clicked_real_publish"):
            if runtime.get(flag) is True:
                raise WorkerError(
                    XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION,
                    f"selector confirmation has forbidden runtime flag {flag}=true",
                )
        if confirmation.get("forbidden_actions_detected"):
            raise WorkerError(
                XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION,
                f"selector confirmation detected forbidden actions: {confirmation.get('forbidden_actions_detected')}",
            )
        confirmed = {item.get("field_key"): item for item in confirmation.get("confirmed_selectors") or []}
        missing = []
        for element in selector_mapping.get("elements", []):
            item = confirmed.get(element["field_key"])
            if not item or item.get("found") is not True or item.get("unique") is not True:
                missing.append(element["field_key"])
            if item and not item.get("selector"):
                raise WorkerError(
                    XHS_YINGDAO_SELECTOR_MAPPING_SELECTOR_EMPTY,
                    f"confirmed selector is empty: {element['field_key']}",
                )
        if missing:
            raise WorkerError(
                XHS_YINGDAO_SELECTOR_MAPPING_ELEMENT_MISSING,
                f"selector confirmation missing fields: {missing}",
            )
        return confirmation

    def verify_mapping(self, job_type: str, job_id: str) -> YingdaoSelectorMappingVerifyResult:
        """Verify selector mapping confirmation and write summary."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_mapping_paths(normalized, job_id)
        selector_mapping = self._read_json(Path(paths["mapping_path"]), XHS_YINGDAO_SELECTOR_MAPPING_ERROR)
        report_text = Path(paths["report_path"]).read_text(encoding="utf-8")
        if "xiaohongshu.com" in report_text.lower():
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_URL, "selector mapping report contains forbidden URL")
        if normalized == "xhs_publish" and "click_publish" in report_text.lower():
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION, "selector mapping report contains forbidden action")
        summary = YingdaoSelectorMappingSummary(element_count=int(selector_mapping.get("element_count", 0)))
        confirmation = None
        status = "verified"
        message = "Yingdao selector mapping confirmation verified"
        error_code = None
        error_message = None
        try:
            confirmation = self.read_mapping_confirmation(normalized, job_id)
            summary.confirmation_exists = True
            self.validate_mapping_confirmation(confirmation, selector_mapping)
            summary.confirmation_valid = True
            summary.confirmed_selector_count = len(confirmation.get("confirmed_selectors") or [])
            runtime = confirmation.get("runtime") or {}
            summary.opened_external_url = bool(runtime.get("opened_external_url", False))
            summary.opened_xhs = bool(runtime.get("opened_xhs", False))
            summary.called_external_api = bool(runtime.get("called_external_api", False))
            summary.clicked_real_publish = bool(runtime.get("clicked_real_publish", False))
            summary.forbidden_actions_detected = confirmation.get("forbidden_actions_detected") or []
        except WorkerError as exc:
            if exc.error_code == XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_NOT_FOUND:
                status = "waiting_selector_confirmation"
                message = "Waiting for selector_mapping_confirmation.json"
            else:
                status = "failed"
                message = "selector_mapping_confirmation.json invalid"
            error_code = exc.error_code
            error_message = exc.error_message
        verify_result = YingdaoSelectorMappingVerifyResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            mapping_dir=paths["mapping_dir"],
            confirmation_path=paths["confirmation_path"],
            selector_mapping_summary_path=paths["summary_path"],
            summary=summary,
            confirmation=confirmation,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        self.write_mapping_summary(self._model_to_dict(verify_result))
        return verify_result

    def write_mock_confirmation(self, job_type: str, job_id: str, status: str = "success") -> dict[str, str]:
        """Write local mock selector confirmation."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_mapping_paths(normalized, job_id)
        selector_mapping = self._read_json(Path(paths["mapping_path"]), XHS_YINGDAO_SELECTOR_MAPPING_ERROR)
        confirmation = self._model_to_dict(
            YingdaoSelectorMappingConfirmation(
                job_type=normalized,
                job_id=job_id,
                status=status,
                confirmed_at=self._utc_now(),
                runtime=YingdaoSelectorMappingRuntime(),
                confirmed_selectors=[
                    {
                        "field_key": element["field_key"],
                        "selector": element["recommended_selector"],
                        "found": True,
                        "unique": True,
                        "action_type": element.get("yingdao_action", {}).get("action_type", "fill"),
                    }
                    for element in selector_mapping.get("elements", [])
                ],
                forbidden_actions_detected=[],
                notes="Confirmed against local HTML sandbox only.",
            )
        )
        return {"confirmation_path": self._write_json(Path(paths["confirmation_path"]), confirmation)}

    def write_mapping_summary(self, summary: dict[str, Any]) -> str:
        """Write selector mapping verification summary."""
        paths = self.get_mapping_paths(str(summary["job_type"]), str(summary["job_id"]))
        return self._write_json(Path(paths["summary_path"]), summary)

    def get_mapping_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return selector mapping paths."""
        normalized = self._normalize_job_type(job_type)
        category = "search" if normalized == "xhs_search" else "publish"
        mapping_dir = self.queue_root / "selector_mapping" / category / job_id
        return {
            "mapping_dir": str(mapping_dir),
            "input_path": str(mapping_dir / "selector_mapping_input.json"),
            "mapping_path": str(mapping_dir / "yingdao_selector_mapping.json"),
            "action_sequence_path": str(mapping_dir / "yingdao_action_sequence.json"),
            "report_path": str(mapping_dir / "selector_mapping_report.md"),
            "confirmation_path": str(mapping_dir / "selector_mapping_confirmation.json"),
            "summary_path": str(mapping_dir / "selector_mapping_summary.json"),
        }

    def _prepare_mapping(
        self,
        job_type: str,
        job_id: str,
        account_id: str,
        payload: dict[str, Any],
    ) -> YingdaoSelectorMappingPrepareResult:
        normalized = self._normalize_job_type(job_type)
        sandbox_bundle = self.load_or_prepare_html_sandbox(normalized, job_id, payload)
        sandbox = sandbox_bundle["sandbox"]
        expected_dom = sandbox_bundle["expected_dom"]
        paths = self.get_mapping_paths(normalized, job_id)
        mapping_input = self._model_to_dict(
            YingdaoSelectorMappingInput(
                job_type=normalized,
                job_id=job_id,
                account_id=account_id,
                created_at=self._utc_now(),
                sandbox_manifest_path=sandbox.manifest_path,
                html_path=sandbox.html_path,
                expected_dom_path=sandbox.expected_dom_path,
                forbidden={
                    "external_network": True,
                    "xiaohongshu_url": True,
                    "real_publish": True,
                    "real_search": True,
                    "yingdao_openapi": True,
                },
            )
        )
        selector_mapping = self.build_selector_mapping(normalized, job_id, sandbox.html_path, expected_dom)
        action_sequence = self.build_action_sequence(selector_mapping)
        report = self.build_markdown_report(selector_mapping, action_sequence)
        self.write_mapping_package(normalized, job_id, mapping_input, selector_mapping, action_sequence, report)
        return YingdaoSelectorMappingPrepareResult(
            job_id=job_id,
            job_type=normalized,
            status="waiting_selector_confirmation",
            mapping_dir=paths["mapping_dir"],
            selector_mapping_input_path=paths["input_path"],
            selector_mapping_path=paths["mapping_path"],
            action_sequence_path=paths["action_sequence_path"],
            mapping_report_path=paths["report_path"],
            confirmation_path=paths["confirmation_path"],
            message="Local HTML selector mapping report prepared; no real page was opened.",
        )

    def _validate_html_text_safety(self, html_content: str, forbidden_text: list[str]) -> None:
        lowered = html_content.lower()
        if "xiaohongshu.com" in lowered or "http://" in lowered or "https://" in lowered:
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_URL, "local HTML contains forbidden URL")
        detected = [text for text in forbidden_text if text and text.lower() in lowered]
        if detected:
            raise WorkerError(
                XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_TEXT,
                f"local HTML contains forbidden text: {detected}",
            )

    def _action_type_for(self, element: dict[str, Any]) -> str:
        if element.get("type") == "checkbox":
            return "set"
        if element.get("tag") == "select":
            return "select"
        return "fill"

    def _expected_value_for(self, element: dict[str, Any]) -> Any:
        if element.get("expected_value") is not None:
            return element.get("expected_value")
        if element.get("expected_value_contains") is not None:
            return element.get("expected_value_contains")
        if element.get("expected_checked") is not None:
            return element.get("expected_checked")
        return None

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
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_ERROR, f"failed to write selector mapping JSON: {path}: {exc}") from exc

    def _write_text(self, path: Path, text: str) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_ERROR, f"failed to write selector mapping report: {path}: {exc}") from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_YINGDAO_SELECTOR_MAPPING_ERROR, f"unsupported selector mapping job_type: {job_type}")

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
