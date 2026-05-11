import json
import os
from typing import Any
from urllib import error, request

from app.utils.errors import (
    XHS_EXTERNAL_LIVE_CHECK_DISABLED,
    XHS_KJVS_DISCOVERY_FAILED,
    XHS_KJVS_RESPONSE_INVALID,
    WorkerError,
)


SENSITIVE_KEY_PARTS = ("token", "cookie", "secret", "key", "password", "authorization")


class KuaJingVSAdapter:
    """Live-readonly KuaJingVS adapter. It only supports safe GET discovery."""

    def __init__(
        self,
        api_base_url: str | None = None,
        api_id: str | None = None,
        api_secret: str | None = None,
        timeout_seconds: int = 10,
        http_client: Any | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Create a KuaJingVS readonly adapter."""
        self.env = env
        self.api_base_url = (api_base_url or self._get("KJVS_API_BASE_URL") or "").strip().rstrip("/")
        if self.api_base_url.endswith("/v1"):
            self.api_base_url = self.api_base_url[:-3].rstrip("/")
        self.api_id = (api_id if api_id is not None else self._get("KJVS_API_ID") or "").strip()
        self.api_secret = (api_secret if api_secret is not None else self._get("KJVS_API_SECRET") or "").strip()
        self.timeout_seconds = min(max(int(timeout_seconds), 1), 10)
        self.http_client = http_client

    def is_live_readonly_enabled(self) -> bool:
        """Return whether live readonly calls are explicitly enabled."""
        return str(self._get("XHS_ALLOW_LIVE_READONLY_CHECKS", "false")).strip().lower() == "true"

    def assert_live_readonly_enabled(self) -> None:
        """Block live readonly calls unless explicitly enabled."""
        if not self.is_live_readonly_enabled():
            raise WorkerError(
                error_code=XHS_EXTERNAL_LIVE_CHECK_DISABLED,
                error_message="KuaJingVS live readonly discovery is disabled. Set XHS_ALLOW_LIVE_READONLY_CHECKS=true.",
                retryable=False,
            )

    def list_shops_readonly(self) -> list[dict]:
        """List KuaJingVS shops through GET /v1/shops only."""
        self.assert_live_readonly_enabled()
        response = self._get_json("/shops?page=1&size=50")
        shops = response.get("shops") or response.get("data") or response.get("records") or []
        if isinstance(shops, dict):
            shops = shops.get("list") or shops.get("items") or shops.get("records") or []
        if not isinstance(shops, list):
            raise WorkerError(
                error_code=XHS_KJVS_RESPONSE_INVALID,
                error_message="KuaJingVS shops response does not contain a list.",
                retryable=False,
            )
        return [self.normalize_shop(shop) for shop in shops if isinstance(shop, dict)]

    def normalize_shop(self, raw: dict) -> dict:
        """Return a sanitized shop record."""
        shop_id = raw.get("shop_id") or raw.get("shopId") or raw.get("id")
        shop_name = raw.get("shop_name") or raw.get("shopName") or raw.get("name")
        safe_keys = [str(key) for key in raw.keys() if not self._is_sensitive_key(str(key))]
        return {
            "shop_id": str(shop_id) if shop_id is not None else None,
            "shop_name": str(shop_name) if shop_name is not None else None,
            "raw_keys": sorted(safe_keys),
        }

    def discover_shops_readonly(self) -> dict:
        """Run shop discovery and return a stable structure."""
        shops = self.list_shops_readonly()
        return {
            "status": "success",
            "mode": "live_readonly",
            "shop_count": len(shops),
            "shops": shops,
        }

    def _get_json(self, path: str) -> dict:
        """GET JSON with short timeout and explicit error mapping."""
        url = f"{self.api_base_url}/v1/{path.lstrip('/')}"
        try:
            if self.http_client is not None:
                response = self.http_client.get_json(url, headers=self._headers())
            else:
                req = request.Request(url, headers=self._headers(), method="GET")
                with request.urlopen(req, timeout=self.timeout_seconds) as raw_response:
                    response = json.loads(raw_response.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkerError(
                error_code=XHS_KJVS_RESPONSE_INVALID,
                error_message=f"KuaJingVS response is not valid JSON: {exc}",
                retryable=False,
            ) from exc
        except (TimeoutError, OSError, error.URLError, error.HTTPError) as exc:
            raise WorkerError(
                error_code=XHS_KJVS_DISCOVERY_FAILED,
                error_message=f"KuaJingVS readonly discovery failed: {exc}",
                retryable=True,
            ) from exc
        except WorkerError:
            raise
        except Exception as exc:
            raise WorkerError(
                error_code=XHS_KJVS_DISCOVERY_FAILED,
                error_message=f"KuaJingVS readonly discovery failed: {exc}",
                retryable=True,
            ) from exc
        if not isinstance(response, dict):
            raise WorkerError(
                error_code=XHS_KJVS_RESPONSE_INVALID,
                error_message="KuaJingVS response must be a JSON object.",
                retryable=False,
            )
        return response

    def _headers(self) -> dict[str, str]:
        """Return KuaJingVS readonly headers without logging values."""
        headers = {}
        if self.api_id:
            headers["x-app-id"] = self.api_id
        if self.api_secret:
            headers["x-app-secret"] = self.api_secret
        return headers

    def _get(self, name: str, default: str | None = None) -> str | None:
        """Read from injected env mapping or process environment."""
        source = self.env if self.env is not None else os.environ
        return source.get(name, default)

    def _is_sensitive_key(self, key: str) -> bool:
        """Return whether a raw response key appears sensitive."""
        lowered = key.lower()
        return any(part in lowered for part in SENSITIVE_KEY_PARTS)
