from typing import Any

from app.utils.errors import ELEMENT_NOT_FOUND, UNKNOWN_ERROR, WorkerError


def clear_and_type(element: Any, text: str) -> None:
    """Clear an element and type text into it."""
    try:
        element.clear()
        element.send_keys(text)
    except AttributeError as exc:
        raise WorkerError(
            error_code=ELEMENT_NOT_FOUND,
            error_message="element does not support clear or send_keys",
            retryable=True,
        ) from exc
    except Exception as exc:
        raise WorkerError(
            error_code=UNKNOWN_ERROR,
            error_message="failed to clear and type text",
            retryable=True,
        ) from exc


def safe_type(element: Any, text: str) -> None:
    """Type text into an element with a click fallback."""
    try:
        element.clear()
        element.send_keys(text)
        return
    except AttributeError:
        pass
    except Exception:
        pass

    try:
        element.click()
        element.send_keys(text)
    except AttributeError as exc:
        raise WorkerError(
            error_code=ELEMENT_NOT_FOUND,
            error_message="element does not support click or send_keys",
            retryable=True,
        ) from exc
    except Exception as exc:
        raise WorkerError(
            error_code=UNKNOWN_ERROR,
            error_message="failed to type text",
            retryable=True,
        ) from exc
