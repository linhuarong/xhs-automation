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


class UnsupportedProviderError(ValueError):
    """Raised when a provider type is not registered."""


class ReservedProvider(BrowserProvider):
    """Provider placeholder for a known but unimplemented route."""

    def __init__(self, provider_type: str, message: str) -> None:
        """Create a reserved provider route."""
        self.provider_type = provider_type
        self.message = message

    def open_profile(self, account_id: str) -> BrowserSession:
        """Reserved providers do not open profiles."""
        raise NotImplementedError(self.message)

    def get_driver(self, session: BrowserSession) -> Any:
        """Reserved providers do not expose drivers."""
        raise NotImplementedError(self.message)

    def check_login(self, driver: Any) -> bool:
        """Reserved providers cannot check login."""
        raise NotImplementedError(self.message)

    def capture_screenshot(self, session: BrowserSession, name: str) -> str:
        """Reserved providers cannot capture screenshots."""
        raise NotImplementedError(self.message)

    def close_profile(self, session: BrowserSession) -> None:
        """Reserved providers have no session to close."""
        return None
