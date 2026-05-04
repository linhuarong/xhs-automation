import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from app.core.xhs_selectors import (
    BODY_TEXT_SELECTOR,
    HUMAN_REQUIRED_SELECTORS,
    HUMAN_REQUIRED_TEXTS,
    RESULT_AREA_SELECTORS,
    RESULT_AUTHOR_SELECTORS,
    RESULT_CARD_SELECTORS,
    RESULT_LINK_SELECTORS,
    RESULT_METRIC_SELECTORS,
    RESULT_TITLE_SELECTORS,
    SEARCH_INPUT_SELECTORS,
    XHS_SEARCH_URL,
)
from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_WAITING_HUMAN_VERIFICATION,
    SearchJob,
    WorkerResult,
)
from app.utils import (
    ELEMENT_NOT_FOUND,
    PROFILE_START_FAILED,
    UNKNOWN_ERROR,
    WAITING_HUMAN_VERIFICATION,
    WorkerError,
    log_job_event,
)

ENTER_KEY = "\ue007"
CTRL_A_KEYS = "\ue009a"
BACKSPACE_KEY = "\ue003"
PAGE_LOAD_WAIT_SECONDS = 2
RESULT_WAIT_SECONDS = 2
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_PATTERN = re.compile(r"\s+")
PUBLISHED_AT_PATTERN = re.compile(
    r"(?P<published_at>(?:\d{4}-\d{2}-\d{2})|(?:\d{2}-\d{2})|(?:\d+\u5929\u524d)|(?:\d+\u5c0f\u65f6\u524d)|(?:\d+\u5206\u949f\u524d)|(?:\u6628\u5929)|(?:\u4eca\u5929)|(?:\u521a\u521a))$"
)
METRIC_TEXT_PATTERN = re.compile(r"(?P<metric>\d+(?:\.\d+)?\s*(?:\u4e07|\u5343|w|W)?)")
BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]
LOCAL_EVIDENCE_ROOT = BROWSER_WORKER_ROOT / ".local_evidence"


def build_search_url(keyword: str) -> str:
    """Build an XHS search URL with an encoded keyword."""
    encoded_keyword = quote(keyword or "", safe="")
    return f"{XHS_SEARCH_URL}?keyword={encoded_keyword}"


def clean_text(value: str | None) -> str | None:
    """Clean visible text from a search result field."""
    if value is None:
        return None

    text = CONTROL_CHAR_PATTERN.sub("", str(value))
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text or None


def _parse_note_url(url: str | None):
    """Parse a note URL, accepting common schemeless XHS URLs."""
    cleaned_url = clean_text(url)
    if cleaned_url is None:
        return None

    if cleaned_url.startswith("//"):
        cleaned_url = f"https:{cleaned_url}"
    elif cleaned_url.startswith("xiaohongshu.com/") or cleaned_url.startswith(
        "www.xiaohongshu.com/"
    ):
        cleaned_url = f"https://{cleaned_url}"

    return urlparse(cleaned_url)


def is_valid_note_url(url: str | None) -> bool:
    """Return whether a URL points to an XHS note-like page."""
    parsed = _parse_note_url(url)
    if parsed is None:
        return False

    hostname = (parsed.hostname or "").lower()
    if hostname != "xiaohongshu.com" and not hostname.endswith(".xiaohongshu.com"):
        return False

    path = parsed.path.rstrip("/")
    if path in {"", "/", "/search_result"}:
        return False

    return path.startswith("/search_result/") or path.startswith("/explore/")


def extract_note_id(note_url: str | None) -> str | None:
    """Extract a note id from a supported XHS note URL."""
    parsed = _parse_note_url(note_url)
    if parsed is None:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None

    if parts[0] not in {"search_result", "explore"}:
        return None

    note_id = clean_text(parts[1])
    return note_id or None


def split_author_and_published_at(author_text: str | None) -> tuple[str | None, str | None]:
    """Split author text into author name and visible publish time text."""
    text = clean_text(author_text)
    if text is None:
        return None, None

    match = PUBLISHED_AT_PATTERN.search(text)
    if match is None:
        return text, None

    published_at_text = match.group("published_at")
    author = clean_text(text[: match.start()])
    return author, published_at_text


def normalize_visible_metrics(visible_metrics: dict | None) -> dict:
    """Normalize visible metric text for downstream records."""
    if not isinstance(visible_metrics, dict):
        return {}

    metric_raw_text = clean_text(visible_metrics.get("text"))
    if metric_raw_text is None:
        return {}

    normalized = {"metric_raw_text": metric_raw_text}
    metric_match = METRIC_TEXT_PATTERN.search(metric_raw_text)
    if metric_match is not None:
        normalized["like_count_text"] = clean_text(metric_match.group("metric"))
    return normalized


def normalize_search_item(raw_item: dict, rank: int) -> dict | None:
    """Normalize and validate one extracted search item."""
    note_url = clean_text(raw_item.get("note_url"))
    if not is_valid_note_url(note_url):
        return None

    visible_metrics = raw_item.get("visible_metrics")
    if not isinstance(visible_metrics, dict):
        visible_metrics = {}

    cleaned_metrics: dict = {}
    for key, value in visible_metrics.items():
        cleaned_value = clean_text(value) if isinstance(value, str) else value
        if cleaned_value is not None:
            cleaned_metrics[key] = cleaned_value

    return {
        "rank": rank,
        "title": clean_text(raw_item.get("title")),
        "author": clean_text(raw_item.get("author")),
        "note_url": note_url,
        "visible_metrics": cleaned_metrics,
    }


def _utc_now_iso() -> str:
    """Return current UTC time as an ISO8601 string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_search_evidence(
    *,
    job: SearchJob,
    status: str,
    search_url: str,
    screenshot_path: str | None,
    items: list[dict],
    result_area_found: bool,
    captured_at: str | None = None,
) -> dict:
    """Build structured local evidence for a search job."""
    evidence = {
        "job_id": job.job_id,
        "task_type": "xhs_keyword_search",
        "status": status,
        "keyword": job.keyword,
        "account_id": job.account_id,
        "provider_type": job.provider_type,
        "captured_at": captured_at or _utc_now_iso(),
        "search_url": search_url,
        "screenshot_path": screenshot_path,
        "item_count": len(items),
        "result_area_found": result_area_found,
        "items": items,
    }
    normalized_records = build_normalized_search_records(evidence)
    evidence["normalized_record_count"] = len(normalized_records)
    evidence["normalized_records"] = normalized_records
    return evidence


def build_normalized_search_records(
    evidence: dict,
    evidence_json_path: str | None = None,
) -> list[dict]:
    """Build normalized records from search evidence items."""
    records: list[dict] = []
    items = evidence.get("items") or []
    if not isinstance(items, list):
        return records

    for item in items:
        if not isinstance(item, dict):
            continue

        note_url = clean_text(item.get("note_url"))
        author, published_at_text = split_author_and_published_at(item.get("author"))
        normalized_metrics = normalize_visible_metrics(item.get("visible_metrics"))
        record = {
            "job_id": evidence.get("job_id"),
            "keyword": evidence.get("keyword"),
            "account_id": evidence.get("account_id"),
            "provider_type": evidence.get("provider_type"),
            "captured_at": evidence.get("captured_at"),
            "rank": len(records) + 1,
            "title": clean_text(item.get("title")),
            "author": author,
            "published_at_text": published_at_text,
            "note_id": extract_note_id(note_url),
            "note_url": note_url,
            "metric_raw_text": normalized_metrics.get("metric_raw_text"),
            "like_count_text": normalized_metrics.get("like_count_text"),
            "screenshot_path": evidence.get("screenshot_path"),
            "evidence_json_path": evidence_json_path,
        }
        records.append(record)

    return records


def save_search_evidence(evidence: dict, job_id: str) -> str:
    """Save search evidence JSON locally and return its path."""
    evidence_dir = LOCAL_EVIDENCE_ROOT / job_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "search_evidence.json"
    evidence["normalized_records"] = build_normalized_search_records(
        evidence,
        evidence_json_path=str(evidence_path),
    )
    evidence["normalized_record_count"] = len(evidence["normalized_records"])
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(evidence_path)


def _find_elements(driver: Any, selector: str) -> list[Any]:
    """Find elements with a CSS selector."""
    try:
        return list(driver.find_elements("css selector", selector))
    except Exception:
        return []


def _find_child_elements(element: Any, selector: str) -> list[Any]:
    """Find child elements with a CSS selector."""
    find_elements = getattr(element, "find_elements", None)
    if find_elements is None:
        return []

    try:
        return list(find_elements("css selector", selector))
    except Exception:
        return []


def _is_visible(element: Any) -> bool:
    """Return whether an element is visible."""
    is_displayed = getattr(element, "is_displayed", None)
    if is_displayed is None:
        return True

    try:
        return bool(is_displayed())
    except Exception:
        return False


def _has_visible_element(driver: Any, selectors: list[str]) -> bool:
    """Return whether any selector has a visible element."""
    for selector in selectors:
        for element in _find_elements(driver, selector):
            if _is_visible(element):
                return True
    return False


def _visible_body_text(driver: Any) -> str:
    """Read visible body text without using page source."""
    body_elements = _find_elements(driver, BODY_TEXT_SELECTOR)
    if not body_elements:
        return ""

    visible_text: list[str] = []
    for element in body_elements:
        if _is_visible(element):
            text = _element_text(element)
            if text:
                visible_text.append(text)
    return "\n".join(visible_text)


def _requires_human_verification(driver: Any) -> bool:
    """Return whether visible page content clearly requires human action."""
    body_text = _visible_body_text(driver)
    if any(text in body_text for text in HUMAN_REQUIRED_TEXTS):
        return True

    return _has_visible_element(driver, HUMAN_REQUIRED_SELECTORS)


def _find_first_element(driver: Any, selectors: list[str]) -> tuple[Any | None, str | None]:
    """Find the first visible element and selector from candidates."""
    for selector in selectors:
        for element in _find_elements(driver, selector):
            if _is_visible(element):
                return element, selector
    return None, None


def _input_value(search_input: Any) -> str | None:
    """Read the current search input value."""
    return _element_attr(search_input, "value")


def ensure_search_input_keyword(search_input: Any, keyword: str) -> None:
    """Ensure the search input contains the keyword using native element methods."""
    current_value = (_input_value(search_input) or "").strip()
    needs_input = current_value in {"", "undefined", "??"} or current_value != keyword

    if not needs_input:
        search_input.send_keys(ENTER_KEY)
        return

    search_input.click()
    try:
        search_input.clear()
        search_input.send_keys(keyword)
    except Exception:
        search_input.click()
        search_input.send_keys(CTRL_A_KEYS)
        search_input.send_keys(BACKSPACE_KEY)
        search_input.send_keys(keyword)

    search_input.send_keys(ENTER_KEY)


def _element_text(element: Any) -> str:
    """Read normalized visible text from an element."""
    return clean_text(getattr(element, "text", "") or "") or ""


def _element_attr(element: Any, name: str) -> str | None:
    """Read an element attribute without raising."""
    get_attribute = getattr(element, "get_attribute", None)
    if get_attribute is None:
        return None

    try:
        value = get_attribute(name)
    except Exception:
        return None

    if value is None:
        return None
    return str(value).strip() or None


def _find_first_child_text(element: Any, selectors: list[str]) -> str | None:
    """Find first visible child text from candidate selectors."""
    for selector in selectors:
        for child in _find_child_elements(element, selector):
            if not _is_visible(child):
                continue
            text = _element_text(child)
            if text:
                return text
    return None


def _find_first_href(element: Any, selectors: list[str]) -> str | None:
    """Find first visible href from a result card."""
    href = _element_attr(element, "href")
    if href:
        return href

    for selector in selectors:
        for child in _find_child_elements(element, selector):
            if not _is_visible(child):
                continue
            href = _element_attr(child, "href")
            if href:
                return href
    return None


def _fallback_title_from_card(element: Any) -> str | None:
    """Use the first visible line from a result card as a title fallback."""
    for line in _element_text(element).splitlines():
        title = clean_text(line)
        if title:
            return title
    return None


def _extract_visible_metrics(element: Any) -> dict:
    """Extract visible metric text from a result card."""
    metrics: list[str] = []
    seen: set[str] = set()
    for selector in RESULT_METRIC_SELECTORS:
        for child in _find_child_elements(element, selector):
            if not _is_visible(child):
                continue
            text = clean_text(_element_text(child))
            if not text or text in seen:
                continue
            seen.add(text)
            metrics.append(text)

    if not metrics:
        return {}
    return {"text": " | ".join(metrics)}


def extract_visible_results(driver: Any, limit: int) -> list[dict]:
    """Extract visible search result cards from the current DOM."""
    if limit <= 0:
        return []

    results: list[dict] = []
    seen_cards: set[int] = set()
    seen_urls: set[str] = set()

    for selector in RESULT_CARD_SELECTORS:
        for card in _find_elements(driver, selector):
            if not _is_visible(card):
                continue

            card_key = id(card)
            if card_key in seen_cards:
                continue
            seen_cards.add(card_key)

            note_url = _find_first_href(card, RESULT_LINK_SELECTORS)

            title = _find_first_child_text(card, RESULT_TITLE_SELECTORS)
            if title is None:
                title = _fallback_title_from_card(card)

            raw_item = {
                "title": title,
                "author": _find_first_child_text(card, RESULT_AUTHOR_SELECTORS),
                "note_url": note_url,
                "visible_metrics": _extract_visible_metrics(card),
            }

            item = normalize_search_item(raw_item, rank=len(results) + 1)
            if item is None:
                continue

            if item["note_url"] in seen_urls:
                continue
            seen_urls.add(item["note_url"])

            results.append(item)

            if len(results) >= limit:
                return results

    return results


def _safe_capture(provider: BrowserProvider, session: BrowserSession, name: str) -> str | None:
    """Capture a screenshot without raising."""
    try:
        return provider.capture_screenshot(session, name)
    except Exception:
        return None


def _log_step(
    job_id: str,
    step: str,
    status: str = "running",
    message: str | None = None,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Write a structured search step log."""
    log_job_event(
        job_id=job_id,
        step=step,
        status=status,
        message=message,
        error_code=error_code,
        extra=extra,
    )


def _capture_with_log(
    job_id: str,
    provider: BrowserProvider,
    session: BrowserSession,
    name: str,
) -> str | None:
    """Capture a screenshot and log the capture step."""
    _log_step(job_id=job_id, step="capture_screenshot", extra={"name": name})
    return _safe_capture(provider, session, name)


def search_xhs_keyword(
    job: SearchJob,
    provider: BrowserProvider,
) -> WorkerResult:
    """Search an XHS keyword through a real browser page."""
    session: BrowserSession | None = None
    _log_step(job_id=job.job_id, step="search_start", status="started", message="xhs search started")

    try:
        _log_step(job_id=job.job_id, step="open_profile")
        try:
            session = provider.open_profile(job.account_id)
        except Exception as exc:
            raise WorkerError(
                error_code=PROFILE_START_FAILED,
                error_message="failed to start browser profile",
                retryable=True,
            ) from exc

        driver = provider.get_driver(session)
        search_url = build_search_url(job.keyword)
        _log_step(job_id=job.job_id, step="open_search_page", extra={"url": search_url})
        driver.get(search_url)
        time.sleep(PAGE_LOAD_WAIT_SECONDS)

        _log_step(job_id=job.job_id, step="check_human_required")
        if _requires_human_verification(driver):
            screenshot_path = _capture_with_log(
                job_id=job.job_id,
                provider=provider,
                session=session,
                name="search_waiting_human",
            )
            _log_step(
                job_id=job.job_id,
                step="check_human_required",
                status=STATUS_WAITING_HUMAN_VERIFICATION,
                message="manual login or confirmation required",
                error_code=WAITING_HUMAN_VERIFICATION,
            )
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_WAITING_HUMAN_VERIFICATION,
                error_code=WAITING_HUMAN_VERIFICATION,
                error_message="login or verification required",
                screenshot_url=screenshot_path,
                items=[],
            )

        _log_step(
            job_id=job.job_id,
            step="find_search_input",
            extra={"selector_count": len(SEARCH_INPUT_SELECTORS)},
        )
        search_input, matched_selector = _find_first_element(driver, SEARCH_INPUT_SELECTORS)
        if search_input is None:
            raise WorkerError(
                error_code=ELEMENT_NOT_FOUND,
                error_message="search input not found",
                retryable=True,
            )

        _log_step(
            job_id=job.job_id,
            step="input_keyword",
            extra={"matched_selector": matched_selector},
        )
        ensure_search_input_keyword(search_input, job.keyword)

        _log_step(job_id=job.job_id, step="wait_results")
        time.sleep(RESULT_WAIT_SECONDS)

        _log_step(job_id=job.job_id, step="check_human_required")
        if _requires_human_verification(driver):
            screenshot_path = _capture_with_log(
                job_id=job.job_id,
                provider=provider,
                session=session,
                name="search_waiting_human",
            )
            _log_step(
                job_id=job.job_id,
                step="check_human_required",
                status=STATUS_WAITING_HUMAN_VERIFICATION,
                message="manual login or confirmation required",
                error_code=WAITING_HUMAN_VERIFICATION,
            )
            return WorkerResult(
                job_id=job.job_id,
                status=STATUS_WAITING_HUMAN_VERIFICATION,
                error_code=WAITING_HUMAN_VERIFICATION,
                error_message="login or verification required",
                screenshot_url=screenshot_path,
                items=[],
            )

        result_area_found = _has_visible_element(driver, RESULT_AREA_SELECTORS)
        screenshot_path = None
        if job.capture_screenshot:
            screenshot_path = _capture_with_log(
                job_id=job.job_id,
                provider=provider,
                session=session,
                name="search_success",
            )

        try:
            items = extract_visible_results(driver, job.limit)
        except Exception as exc:
            items = []
            _log_step(
                job_id=job.job_id,
                step="extract_visible_results",
                status=STATUS_FAILED,
                message=str(exc),
            )
        evidence = build_search_evidence(
            job=job,
            status=STATUS_SUCCESS,
            search_url=search_url,
            screenshot_path=screenshot_path,
            items=items,
            result_area_found=result_area_found,
        )
        evidence_json_path = save_search_evidence(evidence, job.job_id)
        normalized_records = evidence.get("normalized_records", [])
        _log_step(
            job_id=job.job_id,
            step="search_success",
            status=STATUS_SUCCESS,
            message="search completed",
            extra={
                "item_count": len(items),
                "result_area_found": result_area_found,
                "evidence_json_path": evidence_json_path,
            },
        )
        return WorkerResult(
            job_id=job.job_id,
            status=STATUS_SUCCESS,
            message="search completed",
            screenshot_url=screenshot_path,
            evidence_json_path=evidence_json_path,
            normalized_records=normalized_records,
            items=items,
        )

    except WorkerError as exc:
        screenshot_path = (
            _safe_capture(provider, session, "search_error") if session is not None else None
        )
        _log_step(
            job_id=job.job_id,
            step="search_failed",
            status=STATUS_FAILED,
            error_code=exc.error_code,
            message=exc.error_message,
        )
        return WorkerResult(
            job_id=job.job_id,
            status=STATUS_FAILED,
            error_code=exc.error_code,
            error_message=exc.error_message,
            screenshot_url=screenshot_path,
            items=[],
        )
    except Exception as exc:
        screenshot_path = (
            _safe_capture(provider, session, "search_error") if session is not None else None
        )
        _log_step(
            job_id=job.job_id,
            step="search_failed",
            status=STATUS_FAILED,
            error_code=UNKNOWN_ERROR,
            message=str(exc),
        )
        return WorkerResult(
            job_id=job.job_id,
            status=STATUS_FAILED,
            error_code=UNKNOWN_ERROR,
            error_message="unexpected search error",
            screenshot_url=screenshot_path,
            items=[],
        )
    finally:
        if session is not None:
            provider.close_profile(session)
