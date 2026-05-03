from typing import Any

from app.core.xhs_search_core import search_xhs_keyword
from app.providers.base import BrowserProvider, BrowserSession
from app.schemas import STATUS_FAILED, STATUS_SUCCESS, SearchJob
from app.utils import ELEMENT_NOT_FOUND


class FakeElement:
    def __init__(self, text: str = "", displayed: bool = True) -> None:
        self.text = text
        self.displayed = displayed
        self.calls: list[str] = []

    def is_displayed(self) -> bool:
        return self.displayed

    def clear(self) -> None:
        self.calls.append("clear")

    def send_keys(self, value: str) -> None:
        self.calls.append(f"send_keys:{value}")


class FakeDriver:
    def __init__(
        self,
        elements_by_selector: dict[str, list[FakeElement]] | None = None,
        page_source: str = "",
    ) -> None:
        self.elements_by_selector = elements_by_selector or {}
        self.page_source = page_source
        self.opened_urls: list[str] = []

    def get(self, url: str) -> None:
        self.opened_urls.append(url)

    def find_elements(self, by: str, selector: str) -> list[FakeElement]:
        return self.elements_by_selector.get(selector, [])


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


def _search_job() -> SearchJob:
    return SearchJob(
        job_id="search-test-1",
        account_id="xhs_dev_01",
        keyword="eye shadow",
    )


def test_search_xhs_keyword_calls_open_profile(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    search_input = FakeElement()
    driver = FakeDriver({"input[type='search']": [search_input]})
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert provider.opened_accounts == ["xhs_dev_01"]
    assert result.status == STATUS_SUCCESS
    assert provider.closed_sessions


def test_search_xhs_keyword_success_returns_worker_result(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    search_input = FakeElement()
    result_item = FakeElement(text="first visible title")
    driver = FakeDriver(
        {
            "input[type='search']": [search_input],
            "[class*='note-item']": [result_item],
        }
    )
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_SUCCESS
    assert result.message == "search completed"
    assert result.screenshot_url == ".local_screenshots/session-1/search_result.png"
    assert result.items == [{"rank": 1, "title": "first visible title"}]
    assert search_input.calls == ["clear", "send_keys:eye shadow", "send_keys:\ue007"]


def test_search_xhs_keyword_missing_input_returns_failed(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    provider = FakeProvider(FakeDriver())

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == STATUS_FAILED
    assert result.error_code == ELEMENT_NOT_FOUND
    assert result.screenshot_url == ".local_screenshots/session-1/search_error.png"


def test_search_xhs_keyword_verification_returns_waiting(monkeypatch) -> None:
    monkeypatch.setattr("app.core.xhs_search_core.time.sleep", lambda _: None)
    driver = FakeDriver(page_source="\u8bf7\u5148\u767b\u5f55\u540e\u7ee7\u7eed")
    provider = FakeProvider(driver)

    result = search_xhs_keyword(_search_job(), provider)

    assert result.status == "waiting_human_verification"
    assert result.error_code == "WAITING_HUMAN_VERIFICATION"
    assert result.error_message == "login or verification required"
