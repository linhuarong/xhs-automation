import json
from typing import Any
from urllib.parse import quote

import pytest

from app.core import xhs_search_core
from app.core.xhs_selectors import BODY_TEXT_SELECTOR, RESULT_CARD_SELECTORS, SEARCH_INPUT_SELECTORS
from app.core.xhs_search_core import (
    build_search_url,
    build_search_evidence,
    clean_text,
    ensure_search_input_keyword,
    extract_visible_results,
    is_valid_note_url,
    normalize_search_item,
    save_search_evidence,
    search_xhs_keyword,
)
from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    STATUS_WAITING_HUMAN_VERIFICATION,
    SearchJob,
)
from app.utils import ELEMENT_NOT_FOUND, WAITING_HUMAN_VERIFICATION


class FakeElement:
    def __init__(
        self,
        text: str = "",
        displayed: bool = True,
        children_by_selector: dict[str, list["FakeElement"]] | None = None,
        attributes: dict[str, str] | None = None,
        clear_raises: bool = False,
    ) -> None:
        self.text = text
        self.displayed = displayed
        self.children_by_selector = children_by_selector or {}
        self.attributes = attributes or {}
        self.clear_raises = clear_raises
        self.calls: list[str] = []

    def is_displayed(self) -> bool:
        return self.displayed

    def click(self) -> None:
        self.calls.append("click")

    def clear(self) -> None:
        self.calls.append("clear")
        if self.clear_raises:
            raise RuntimeError("clear failed")
        self.attributes["value"] = ""

    def send_keys(self, *values: str) -> None:
        for value in values:
            self.calls.append(f"send_keys:{value}")
            if value == "\ue009a":
                self.attributes["value"] = ""
                continue
            if value == "\ue003":
                self.attributes["value"] = self.attributes.get("value", "")[:-1]
                continue
            if value != "\ue007":
                self.attributes["value"] = self.attributes.get("value", "") + value

    def find_elements(self, by: str, selector: str) -> list["FakeElement"]:
        return self.children_by_selector.get(selector, [])

    def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)


class FakeDriver:
    def __init__(
        self,
        elements_by_selector: dict[str, list[FakeElement]] | None = None,
        page_source: str = "",
    ) -> None:
        self.elements_by_selector = elements_by_selector or {}
        self.page_source = page_source
        self.opened_urls: list[str] = []
        self.searched_selectors: list[str] = []

    def get(self, url: str) -> None:
        self.opened_urls.append(url)

    def find_elements(self, by: str, selector: str) -> list[FakeElement]:
        self.searched_selectors.append(selector)
        return self.elements_by_selector.get(selector, [])

    def execute_script(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("execute_script should not be used")


class FakeProvider(BrowserProvider):
    def __init__(self, driver: FakeDriver, open_raises: bool = False) -> None:
        self.driver = driver
        self.open_raises = open_raises
        self.opened_accounts: list[str] = []
        self.closed_sessions: list[BrowserSession] = []
        self.screenshots: list[str] = []

    def open_profile(self, account_id: str) -> BrowserSession:
        if self.open_raises:
            raise RuntimeError("profile failed")
        self.opened_accounts.append(account_id)
        return BrowserSession(
            account_id=account_id,
            provider_type="fake",
            session_id="session-1",
        )

    def get_driver(self, session: BrowserSession) -> Any:
        return self.driver

    def check_login(self, driver: Any) -> bool:
        return False

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        path = f".local_screenshots/{session.session_id}/{name}.png"
        self.screenshots.append(path)
        return path

    def close_profile(self, session: BrowserSession) -> None:
        self.closed_sessions.append(session)


@pytest.fixture(autouse=True)
def _local_evidence_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xhs_search_core, "LOCAL_EVIDENCE_ROOT", tmp_path / ".local_evidence")


def _search_job() -> SearchJob:
    return SearchJob(
        job_id="search-test-1",
        account_id="xhs_dev_01",
        keyword="eye shadow",
    )


def test_build_search_url_encodes_keyword_without_undefined() -> None:
    url = build_search_url("\u773c\u5f71")

    assert "undefined" not in url
    assert "keyword=" in url
    assert quote("\u773c\u5f71", safe="") in url


def test_clean_text_normalizes_spaces_and_empty_values() -> None:
    assert clean_text("  title\twith\nspaces  ") == "title with spaces"
    assert clean_text("\x00a\x1fb") == "ab"
    assert clean_text("") is None
    assert clean_text(" \n\t ") is None
    assert clean_text(None) is None


def test_is_valid_note_url() -> None:
    assert is_valid_note_url("xiaohongshu.com/search_result/abc") is True
    assert is_valid_note_url("https://www.xiaohongshu.com/explore/abc") is True
    assert is_valid_note_url("https://xiaohongshu.com/search_result") is False
    assert is_valid_note_url("https://example.com/explore/abc") is False
    assert is_valid_note_url("") is False


def test_normalize_search_item_returns_standard_item() -> None:
    item = normalize_search_item(
        {
            "title": "  first\n title ",
            "author": "\t author one ",
            "note_url": "https://www.xiaohongshu.com/explore/abc",
            "visible_metrics": {"text": "  12\nlikes "},
        },
        rank=3,
    )

    assert item == {
        "rank": 3,
        "title": "first title",
        "author": "author one",
        "note_url": "https://www.xiaohongshu.com/explore/abc",
        "visible_metrics": {"text": "12 likes"},
    }


def test_normalize_search_item_filters_invalid_url() -> None:
    assert normalize_search_item({"note_url": "https://example.com/a"}, rank=1) is None


def test_normalize_search_item_keeps_empty_title_with_valid_url() -> None:
    item = normalize_search_item(
        {
            "title": "",
            "author": None,
            "note_url": "https://www.xiaohongshu.com/explore/abc",
        },
        rank=1,
    )

    assert item == {
        "rank": 1,
        "title": None,
        "author": None,
        "note_url": "https://www.xiaohongshu.com/explore/abc",
        "visible_metrics": {},
    }


def test_build_search_evidence_fields_complete() -> None:
    items = [
        {
            "rank": 1,
            "title": "\u773c\u5f71\u6d4b\u8bd5",
            "author": "author one",
            "note_url": "https://www.xiaohongshu.com/explore/abc",
            "visible_metrics": {},
        }
    ]
    job = SearchJob(
        job_id="search-evidence-1",
        account_id="xhs_dev_01",
        keyword="\u773c\u5f71",
    )

    evidence = build_search_evidence(
        job=job,
        status=STATUS_SUCCESS,
        search_url="https://www.xiaohongshu.com/search_result?keyword=x",
        screenshot_path=".local_screenshots/session/search_success.png",
        items=items,
        result_area_found=True,
        captured_at="2026-05-04T00:00:00Z",
    )

    assert evidence == {
        "job_id": "search-evidence-1",
        "task_type": "xhs_keyword_search",
        "status": "success",
        "keyword": "\u773c\u5f71",
        "account_id": "xhs_dev_01",
        "provider_type": "selenium_chrome",
        "captured_at": "2026-05-04T00:00:00Z",
        "search_url": "https://www.xiaohongshu.com/search_result?keyword=x",
        "screenshot_path": ".local_screenshots/session/search_success.png",
        "item_count": 1,
        "result_area_found": True,
        "items": items,
    }


def test_save_search_evidence_writes_utf8_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xhs_search_core, "LOCAL_EVIDENCE_ROOT", tmp_path / ".local_evidence")
    evidence = {
        "job_id": "search-evidence-utf8",
        "keyword": "\u773c\u5f71",
        "item_count": 1,
        "items": [{"title": "\u4e2d\u6587\u6807\u9898"}],
    }

    evidence_path = save_search_evidence(evidence, "search-evidence-utf8")
    evidence_text = (tmp_path / ".local_evidence" / "search-evidence-utf8" / "search_evidence.json").read_text(
        encoding="utf-8"
    )

    assert evidence_path.endswith("search_evidence.json")
    assert "\\u773c" not in evidence_text
    assert "\u773c\u5f71" in evidence_text
    assert json.loads(evidence_text)["item_count"] == 1


def _result_card(
    title: str | None = None,
    author: str | None = None,
    href: str | None = None,
    metric: str | None = None,
    text: str = "",
) -> FakeElement:
    children: dict[str, list[FakeElement]] = {}
    if title is not None:
        children["[class*='title']"] = [FakeElement(text=title)]
    if author is not None:
        children["[class*='author']"] = [FakeElement(text=author)]
    if href is not None:
        children["a[href*='/explore/']"] = [
            FakeElement(text=title or "", attributes={"href": href})
        ]
    if metric is not None:
        children["[class*='like']"] = [FakeElement(text=metric)]
    return FakeElement(text=text, children_by_selector=children)


def test_extract_visible_results_respects_limit() -> None:
    cards = [
        _result_card(
            title="first title",
            author="author one",
            href="https://www.xiaohongshu.com/explore/1",
            metric="12 likes",
        ),
        _result_card(
            title="second title",
            author="author two",
            href="https://www.xiaohongshu.com/explore/2",
            metric="34 likes",
        ),
        _result_card(
            title="third title",
            author="author three",
            href="https://www.xiaohongshu.com/explore/3",
            metric="56 likes",
        ),
    ]
    driver = FakeDriver({RESULT_CARD_SELECTORS[0]: cards})

    results = extract_visible_results(driver, limit=2)

    assert results == [
        {
            "rank": 1,
            "title": "first title",
            "author": "author one",
            "note_url": "https://www.xiaohongshu.com/explore/1",
            "visible_metrics": {"text": "12 likes"},
        },
        {
            "rank": 2,
            "title": "second title",
            "author": "author two",
            "note_url": "https://www.xiaohongshu.com/explore/2",
            "visible_metrics": {"text": "34 likes"},
        },
    ]


def test_extract_visible_results_allows_missing_title_and_author() -> None:
    driver = FakeDriver(
        {
            RESULT_CARD_SELECTORS[0]: [
                _result_card(href="https://www.xiaohongshu.com/explore/abc")
            ]
        }
    )

    results = extract_visible_results(driver, limit=1)

    assert results == [
        {
            "rank": 1,
            "title": None,
            "author": None,
            "note_url": "https://www.xiaohongshu.com/explore/abc",
            "visible_metrics": {},
        }
    ]


def test_extract_visible_results_filters_invalid_cards_and_reranks() -> None:
    cards = [
        _result_card(title="invalid", href="https://example.com/explore/bad"),
        _result_card(title="valid one", href="https://www.xiaohongshu.com/explore/one"),
        _result_card(title="search page", href="https://www.xiaohongshu.com/search_result"),
        _result_card(title="valid two", href="https://www.xiaohongshu.com/search_result/two"),
    ]
    driver = FakeDriver({RESULT_CARD_SELECTORS[0]: cards})

    results = extract_visible_results(driver, limit=5)

    assert results == [
        {
            "rank": 1,
            "title": "valid one",
            "author": None,
            "note_url": "https://www.xiaohongshu.com/explore/one",
            "visible_metrics": {},
        },
        {
            "rank": 2,
            "title": "valid two",
            "author": None,
            "note_url": "https://www.xiaohongshu.com/search_result/two",
            "visible_metrics": {},
        },
    ]


def test_ensure_search_input_keyword_replaces_undefined_value() -> None:
    search_input = FakeElement(attributes={"value": "undefined"})

    ensure_search_input_keyword(search_input, "eye shadow")

    assert search_input.attributes["value"] == "eye shadow"
    assert search_input.calls == ["click", "clear", "send_keys:eye shadow", "send_keys:\ue007"]


def test_ensure_search_input_keyword_replaces_question_marks_value() -> None:
    search_input = FakeElement(attributes={"value": "??"})

    ensure_search_input_keyword(search_input, "eye shadow")

    assert search_input.attributes["value"] == "eye shadow"
    assert search_input.calls == ["click", "clear", "send_keys:eye shadow", "send_keys:\ue007"]


def test_ensure_search_input_keyword_sends_enter_when_value_matches() -> None:
    search_input = FakeElement(attributes={"value": "eye shadow"})

    ensure_search_input_keyword(search_input, "eye shadow")

    assert search_input.attributes["value"] == "eye shadow"
    assert search_input.calls == ["send_keys:\ue007"]


def test_ensure_search_input_keyword_falls_back_when_clear_fails() -> None:
    search_input = FakeElement(attributes={"value": "undefined"}, clear_raises=True)

    ensure_search_input_keyword(search_input, "eye shadow")

    assert search_input.attributes["value"] == "eye shadow"
    assert search_input.calls == [
        "click",
        "clear",
        "click",
        "send_keys:\ue009a",
        "send_keys:\ue003",
        "send_keys:eye shadow",
        "send_keys:\ue007",
    ]


def test_search_xhs_keyword_calls_open_profile(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    search_input = FakeElement()
    driver = FakeDriver({"input[type='search']": [search_input]})
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert provider.opened_accounts == ["xhs_dev_01"]
    assert result.status == STATUS_SUCCESS
    assert quote("eye shadow", safe="") in driver.opened_urls[0]
    assert provider.closed_sessions


def test_search_xhs_keyword_success_returns_worker_result(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    search_input = FakeElement()
    result_item = _result_card(
        title="first visible title",
        author="author one",
        href="https://www.xiaohongshu.com/explore/1",
        metric="12 likes",
    )
    driver = FakeDriver(
        {
            "input[type='search']": [search_input],
            RESULT_CARD_SELECTORS[0]: [result_item],
        }
    )
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_SUCCESS
    assert result.message == "search completed"
    assert result.screenshot_url == ".local_screenshots/session-1/search_success.png"
    assert result.items == [
        {
            "rank": 1,
            "title": "first visible title",
            "author": "author one",
            "note_url": "https://www.xiaohongshu.com/explore/1",
            "visible_metrics": {"text": "12 likes"},
        }
    ]
    assert search_input.calls == ["click", "clear", "send_keys:eye shadow", "send_keys:\ue007"]


def test_search_xhs_keyword_does_not_treat_page_source_login_as_waiting(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    search_input = FakeElement()
    driver = FakeDriver(
        {"input[type='search']": [search_input]},
        page_source="\u767b\u5f55",
    )
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_SUCCESS
    assert result.error_code is None


def test_search_xhs_keyword_visible_login_prompt_returns_waiting(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    driver = FakeDriver(
        {BODY_TEXT_SELECTOR: [FakeElement(text="\u8bf7\u5148\u767b\u5f55\u540e\u7ee7\u7eed")]}
    )
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_WAITING_HUMAN_VERIFICATION
    assert result.error_code == WAITING_HUMAN_VERIFICATION
    assert result.error_message == "login or verification required"


def test_search_xhs_keyword_clears_undefined_input_value(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    search_input = FakeElement(attributes={"value": "undefined"})
    driver = FakeDriver({"input[type='search']": [search_input]})
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_SUCCESS
    assert search_input.attributes["value"] == "eye shadow"
    assert search_input.calls == ["click", "clear", "send_keys:eye shadow", "send_keys:\ue007"]


def test_search_xhs_keyword_tries_multiple_selectors_until_success(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    final_selector = SEARCH_INPUT_SELECTORS[-1]
    search_input = FakeElement()
    driver = FakeDriver({final_selector: [search_input]})
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    input_selector_attempts = [
        selector for selector in driver.searched_selectors if selector in SEARCH_INPUT_SELECTORS
    ]
    assert result.status == STATUS_SUCCESS
    assert input_selector_attempts == SEARCH_INPUT_SELECTORS
    assert search_input.calls == ["click", "clear", "send_keys:eye shadow", "send_keys:\ue007"]


def test_search_xhs_keyword_missing_input_returns_failed(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    driver = FakeDriver()
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    input_selector_attempts = [
        selector for selector in driver.searched_selectors if selector in SEARCH_INPUT_SELECTORS
    ]
    assert result.status == STATUS_FAILED
    assert result.error_code == ELEMENT_NOT_FOUND
    assert input_selector_attempts == SEARCH_INPUT_SELECTORS
    assert result.screenshot_url == ".local_screenshots/session-1/search_error.png"


def test_search_xhs_keyword_verification_returns_waiting(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    driver = FakeDriver(
        {BODY_TEXT_SELECTOR: [FakeElement(text="\u8bf7\u5148\u767b\u5f55\u540e\u7ee7\u7eed")]}
    )
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_WAITING_HUMAN_VERIFICATION
    assert result.error_code == WAITING_HUMAN_VERIFICATION
    assert result.error_message == "login or verification required"
    assert result.screenshot_url == ".local_screenshots/session-1/search_waiting_human.png"
