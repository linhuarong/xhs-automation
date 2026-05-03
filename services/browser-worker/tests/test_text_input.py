import pytest

from app.utils import ELEMENT_NOT_FOUND, UNKNOWN_ERROR, WorkerError
from app.utils.text_input import clear_and_type, safe_type


class FakeElement:
    def __init__(
        self,
        clear_raises: Exception | None = None,
        click_raises: Exception | None = None,
        send_keys_raises: Exception | None = None,
    ) -> None:
        self.clear_raises = clear_raises
        self.click_raises = click_raises
        self.send_keys_raises = send_keys_raises
        self.calls: list[str] = []

    def clear(self) -> None:
        self.calls.append("clear")
        if self.clear_raises:
            raise self.clear_raises

    def click(self) -> None:
        self.calls.append("click")
        if self.click_raises:
            raise self.click_raises

    def send_keys(self, text: str) -> None:
        self.calls.append(f"send_keys:{text}")
        if self.send_keys_raises:
            raise self.send_keys_raises


class ClickOnlyElement:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def click(self) -> None:
        self.calls.append("click")

    def send_keys(self, text: str) -> None:
        self.calls.append(f"send_keys:{text}")


def test_clear_and_type_uses_clear_then_send_keys() -> None:
    element = FakeElement()

    clear_and_type(element, "hello")

    assert element.calls == ["clear", "send_keys:hello"]


def test_clear_and_type_raises_element_not_found_for_missing_methods() -> None:
    with pytest.raises(WorkerError) as exc_info:
        clear_and_type(object(), "hello")

    assert exc_info.value.error_code == ELEMENT_NOT_FOUND


def test_clear_and_type_wraps_runtime_failure() -> None:
    element = FakeElement(send_keys_raises=RuntimeError("typing failed"))

    with pytest.raises(WorkerError) as exc_info:
        clear_and_type(element, "hello")

    assert exc_info.value.error_code == UNKNOWN_ERROR


def test_safe_type_uses_clear_when_available() -> None:
    element = FakeElement()

    safe_type(element, "hello")

    assert element.calls == ["clear", "send_keys:hello"]


def test_safe_type_falls_back_to_click_when_clear_missing() -> None:
    element = ClickOnlyElement()

    safe_type(element, "hello")

    assert element.calls == ["click", "send_keys:hello"]


def test_safe_type_falls_back_to_click_when_clear_fails() -> None:
    element = FakeElement(clear_raises=RuntimeError("clear failed"))

    safe_type(element, "hello")

    assert element.calls == ["clear", "click", "send_keys:hello"]


def test_safe_type_raises_element_not_found_for_missing_methods() -> None:
    with pytest.raises(WorkerError) as exc_info:
        safe_type(object(), "hello")

    assert exc_info.value.error_code == ELEMENT_NOT_FOUND
