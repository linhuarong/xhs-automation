from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class BrowserSession:
    """Browser profile session metadata."""

    account_id: str
    provider_type: str
    session_id: str | None = None
    metadata: dict[str, Any] | None = None


class BrowserProvider(ABC):
    """Abstract browser provider contract."""

    @abstractmethod
    def open_profile(self, account_id: str) -> BrowserSession:
        """Open a browser profile for an account."""

    @abstractmethod
    def get_driver(self, session: BrowserSession) -> Any:
        """Return the underlying browser driver."""

    @abstractmethod
    def check_login(self, driver: Any) -> bool:
        """Check whether the browser is logged in."""

    @abstractmethod
    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """Capture a screenshot and return its path or key."""

    @abstractmethod
    def close_profile(self, session: BrowserSession) -> None:
        """Close the browser profile session."""
