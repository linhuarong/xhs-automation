import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.providers.base import BrowserProvider, BrowserSession


class SeleniumChromeProvider(BrowserProvider):
    """Local development Chrome provider using Selenium WebDriver."""

    provider_type = "selenium_chrome"

    def __init__(
        self,
        profile_root: str | None = None,
        screenshot_root: str | None = None,
    ) -> None:
        """Create a local Chrome provider."""
        self.profile_root = Path(
            profile_root or os.getenv("LOCAL_PROFILE_ROOT", ".local_profiles")
        )
        self.screenshot_root = Path(
            screenshot_root or os.getenv("LOCAL_SCREENSHOT_ROOT", ".local_screenshots")
        )
        self._drivers: dict[str, Any] = {}

    def open_profile(self, account_id: str) -> BrowserSession:
        """Open a local Chrome profile for an account."""
        profile_dir = self.profile_root / account_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        session_id = uuid4().hex
        options = Options()
        options.add_argument(f"--user-data-dir={profile_dir.resolve()}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

        driver = webdriver.Chrome(options=options)
        self._drivers[session_id] = driver

        return BrowserSession(
            account_id=account_id,
            provider_type=self.provider_type,
            session_id=session_id,
            metadata={"profile_dir": str(profile_dir)},
        )

    def get_driver(self, session: BrowserSession) -> Any:
        """Return the Selenium driver for a session."""
        if session.session_id is None:
            raise ValueError("BrowserSession.session_id is required.")
        return self._drivers[session.session_id]

    def check_login(self, driver: Any) -> bool:
        """Return the current login state placeholder."""
        return False

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """Save a local screenshot and return the file path."""
        if session.session_id is None:
            raise ValueError("BrowserSession.session_id is required.")

        driver = self.get_driver(session)
        screenshot_dir = self.screenshot_root / session.session_id
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        screenshot_path = screenshot_dir / f"{name}.png"
        driver.save_screenshot(str(screenshot_path))
        return str(screenshot_path)

    def close_profile(self, session: BrowserSession) -> None:
        """Close the Selenium driver for a session."""
        if session.session_id is None:
            return

        driver = self._drivers.pop(session.session_id, None)
        if driver is not None:
            driver.quit()
