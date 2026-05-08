import json
import os
import time
from pathlib import Path
from typing import Any

from app.services.yingdao_service import UrllibJsonClient
from app.utils.errors import (
    KJVS_CONFIG_ERROR,
    KJVS_ENV_FAILED,
    KJVS_ENV_TIMEOUT,
    KJVS_PROFILE_NOT_FOUND,
    WorkerError,
)


class KuaJingVSService:
    """KuaJingVS OpenAPI skeleton with mockable HTTP calls."""

    def __init__(
        self,
        api_base_url: str | None = None,
        api_id: str | None = None,
        api_secret: str | None = None,
        profile_map_path: str | None = None,
        ready_timeout_seconds: int | None = None,
        poll_interval_seconds: int | None = None,
        http_client: Any | None = None,
    ) -> None:
        """Create a KuaJingVS service from environment-backed config."""
        self.api_base_url = (
            api_base_url or os.getenv("KJVS_API_BASE_URL") or "http://127.0.0.1:49709"
        ).rstrip("/")
        self.api_id = api_id or os.getenv("KJVS_API_ID", "")
        self.api_secret = api_secret or os.getenv("KJVS_API_SECRET", "")
        self.profile_map_path = profile_map_path or os.getenv("KJVS_PROFILE_MAP_PATH", "")
        self.ready_timeout_seconds = self._parse_int_config(
            "KJVS_ENV_READY_TIMEOUT_SECONDS",
            ready_timeout_seconds,
            default=120,
        )
        self.poll_interval_seconds = self._parse_int_config(
            "KJVS_ENV_POLL_INTERVAL_SECONDS",
            poll_interval_seconds,
            default=2,
        )
        self.http_client = http_client or UrllibJsonClient()

    def _parse_int_config(self, env_name: str, value: int | None, default: int) -> int:
        """Parse integer KuaJingVS config."""
        raw_value = value if value is not None else os.getenv(env_name, str(default))
        try:
            parsed_value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise WorkerError(
                error_code=KJVS_CONFIG_ERROR,
                error_message=f"{env_name} must be an integer.",
                retryable=False,
            ) from exc
        if parsed_value < 0:
            raise WorkerError(
                error_code=KJVS_CONFIG_ERROR,
                error_message=f"{env_name} must be greater than or equal to 0.",
                retryable=False,
            )
        return parsed_value

    def _headers(self) -> dict[str, str]:
        """Build KuaJingVS request headers."""
        return {
            "X-Api-Id": self.api_id,
            "X-Api-Secret": self.api_secret,
        }

    def _load_profile_map(self) -> dict:
        """Load account to shop mapping from JSON."""
        if not self.profile_map_path:
            raise WorkerError(
                error_code=KJVS_CONFIG_ERROR,
                error_message="KJVS_PROFILE_MAP_PATH is not configured.",
                retryable=False,
            )
        path = Path(self.profile_map_path)
        try:
            profile_map = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(
                error_code=KJVS_CONFIG_ERROR,
                error_message=f"KJVS profile map not found: {path}",
                retryable=False,
            ) from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(
                error_code=KJVS_CONFIG_ERROR,
                error_message=f"KJVS profile map is invalid JSON: {path}",
                retryable=False,
            ) from exc
        if not isinstance(profile_map, dict):
            raise WorkerError(
                error_code=KJVS_CONFIG_ERROR,
                error_message="KJVS profile map must be a JSON object.",
                retryable=False,
            )
        return profile_map

    def list_shops(self) -> list[dict]:
        """List shops through the KuaJingVS HTTP contract."""
        response = self.http_client.get_json(
            f"{self.api_base_url}/shops",
            headers=self._headers(),
        )
        shops = response.get("shops") or response.get("data") or []
        return shops if isinstance(shops, list) else []

    def resolve_shop_id(self, account_id: str) -> str:
        """Resolve a shop id for an account id."""
        profile_map = self._load_profile_map()
        profile = profile_map.get(account_id)
        if not isinstance(profile, dict) or not profile.get("shop_id"):
            raise WorkerError(
                error_code=KJVS_PROFILE_NOT_FOUND,
                error_message=f"KuaJingVS profile not found for account_id: {account_id}",
                retryable=False,
            )
        return str(profile["shop_id"])

    def open_shop(self, shop_id: str) -> dict:
        """Open a KuaJingVS shop environment through HTTP contract."""
        return self.http_client.post_json(
            f"{self.api_base_url}/shops/{shop_id}/open",
            {},
            headers=self._headers(),
        )

    def close_shop(self, shop_id: str) -> dict:
        """Close a KuaJingVS shop environment through HTTP contract."""
        return self.http_client.post_json(
            f"{self.api_base_url}/shops/{shop_id}/close",
            {},
            headers=self._headers(),
        )

    def wait_environment_ready(
        self,
        shop_id: str,
        timeout_seconds: int | None = None,
    ) -> dict:
        """Poll KuaJingVS until the environment is ready."""
        timeout = timeout_seconds if timeout_seconds is not None else self.ready_timeout_seconds
        deadline = time.monotonic() + timeout
        while time.monotonic() <= deadline:
            response = self.http_client.get_json(
                f"{self.api_base_url}/shops/{shop_id}/status",
                headers=self._headers(),
            )
            status = str(response.get("status", "")).lower()
            if status in {"ready", "running", "opened", "success"}:
                return response
            if status in {"failed", "error", "closed"}:
                message = response.get("error_message") or response.get("message") or status
                raise WorkerError(
                    error_code=KJVS_ENV_FAILED,
                    error_message=f"KuaJingVS environment {shop_id} failed: {message}",
                    retryable=True,
                )
            time.sleep(self.poll_interval_seconds)
        raise WorkerError(
            error_code=KJVS_ENV_TIMEOUT,
            error_message=f"KuaJingVS environment {shop_id} timed out after {timeout} seconds.",
            retryable=True,
        )
