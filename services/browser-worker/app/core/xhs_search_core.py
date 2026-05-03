import time
from typing import Any

from app.core.xhs_selectors import (
    HUMAN_REQUIRED_SELECTORS,
    RESULT_AREA_SELECTORS,
    RESULT_ITEM_SELECTORS,
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
PAGE_LOAD_WAIT_SECONDS = 2
RESULT_WAIT_SECONDS = 2


def _find_elements(driver: Any, selector: str) -> list[Any]:
    """Find elements with a CSS selector."""
    try:
        return list(driver.find_elements("css selector", selector))
    except Exception:
        return []


def _has_visible_element(driver: Any, selectors: list[str]) -> bool:
    """Return whether any selector has a visible element."""
    for selector in selectors:
        if selector.startswith("text="):
            text = selector.removeprefix("text=")
            page_source = getattr(driver, "page_source", "") or ""
            if text in page_source:
                return True
            continue

        for element in _find_elements(driver, selector):
            is_displayed = getattr(element, "is_displayed", None)
            if is_displayed is None or is_displayed():
                return True
    return False


def _find_first_element(driver: Any, selectors: list[str]) -> tuple[Any | None, str | None]:
    """Find the first visible element and selector from candidates."""
    for selector in selectors:
        for element in _find_elements(driver, selector):
            is_displayed = getattr(element, "is_displayed", None)
            if is_displayed is None or is_displayed():
                return element, selector
    return None, None


def _extract_visible_items(driver: Any, limit: int) -> list[dict]:
    """Extract visible result item text."""
    items: list[dict] = []
    seen: set[str] = set()
    for selector in RESULT_ITEM_SELECTORS:
        for element in _find_elements(driver, selector):
            text = (getattr(element, "text", "") or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            items.append({"rank": len(items) + 1, "title": text})
            if len(items) >= limit:
                return items
    return items


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
        _log_step(job_id=job.job_id, step="open_search_page", extra={"url": XHS_SEARCH_URL})
        driver.get(XHS_SEARCH_URL)
        time.sleep(PAGE_LOAD_WAIT_SECONDS)

        _log_step(job_id=job.job_id, step="check_human_required")
        if _has_visible_element(driver, HUMAN_REQUIRED_SELECTORS):
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
        search_input.clear()
        search_input.send_keys(job.keyword)
        search_input.send_keys(ENTER_KEY)

        _log_step(job_id=job.job_id, step="wait_results")
        time.sleep(RESULT_WAIT_SECONDS)

        _log_step(job_id=job.job_id, step="check_human_required")
        if _has_visible_element(driver, HUMAN_REQUIRED_SELECTORS):
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

        items = _extract_visible_items(driver, job.limit)
        _log_step(
            job_id=job.job_id,
            step="search_success",
            status=STATUS_SUCCESS,
            message="search completed",
            extra={"item_count": len(items), "result_area_found": result_area_found},
        )
        return WorkerResult(
            job_id=job.job_id,
            status=STATUS_SUCCESS,
            message="search completed",
            screenshot_url=screenshot_path,
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
