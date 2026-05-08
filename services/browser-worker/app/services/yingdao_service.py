import json
import os
import time
from typing import Any
from urllib import request


class UrllibJsonClient:
    """Small JSON HTTP client used by YingdaoService."""

    def post_json(
        self,
        url: str,
        payload: dict,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """POST JSON and return a decoded JSON object."""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """GET JSON and return a decoded JSON object."""
        req = request.Request(url, headers=headers or {}, method="GET")
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))


class YingdaoService:
    """Client wrapper for Yingdao RPA job orchestration."""

    def __init__(
        self,
        api_base_url: str | None = None,
        access_key_id: str | None = None,
        access_key_secret: str | None = None,
        account_name: str | None = None,
        robot_uuid: str | None = None,
        poll_interval_seconds: float | None = None,
        timeout_seconds: int | None = None,
        http_client: Any | None = None,
    ) -> None:
        """Create a Yingdao service from environment-backed configuration."""
        self.api_base_url = (
            api_base_url or os.getenv("YINGDAO_API_BASE_URL") or "https://api.winrobot360.com"
        ).rstrip("/")
        self.access_key_id = access_key_id or os.getenv("YINGDAO_ACCESS_KEY_ID", "")
        self.access_key_secret = access_key_secret or os.getenv("YINGDAO_ACCESS_KEY_SECRET", "")
        self.account_name = account_name or os.getenv("YINGDAO_ACCOUNT_NAME", "")
        self.robot_uuid = robot_uuid or os.getenv("YINGDAO_ROBOT_UUID", "")
        self.poll_interval_seconds = float(
            poll_interval_seconds
            if poll_interval_seconds is not None
            else os.getenv("YINGDAO_JOB_POLL_INTERVAL_SECONDS", "2")
        )
        self.timeout_seconds = int(
            timeout_seconds
            if timeout_seconds is not None
            else os.getenv("YINGDAO_JOB_TIMEOUT_SECONDS", "300")
        )
        self.http_client = http_client or UrllibJsonClient()
        self._access_token: str | None = None

    def get_access_token(self) -> str:
        """Return an access token from Yingdao."""
        if self._access_token:
            return self._access_token

        response = self.http_client.post_json(
            f"{self.api_base_url}/openapi/token",
            {
                "access_key_id": self.access_key_id,
                "access_key_secret": self.access_key_secret,
            },
        )
        token = response.get("access_token") or response.get("token")
        if not token:
            raise RuntimeError("Yingdao access token missing from response.")
        self._access_token = str(token)
        return self._access_token

    def start_job(
        self,
        account_name: str,
        robot_uuid: str,
        params: list[dict],
    ) -> dict:
        """Start a Yingdao RPA job."""
        token = self.get_access_token()
        return self.http_client.post_json(
            f"{self.api_base_url}/openapi/jobs",
            {
                "account_name": account_name,
                "robot_uuid": robot_uuid,
                "params": params,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    def query_job(self, job_uuid: str) -> dict:
        """Query a Yingdao RPA job."""
        token = self.get_access_token()
        return self.http_client.get_json(
            f"{self.api_base_url}/openapi/jobs/{job_uuid}",
            headers={"Authorization": f"Bearer {token}"},
        )

    def wait_job_done(
        self,
        job_uuid: str,
        timeout_seconds: int | None = None,
    ) -> dict:
        """Poll a Yingdao job until it reaches a terminal state."""
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        deadline = time.monotonic() + timeout
        while time.monotonic() <= deadline:
            result = self.query_job(job_uuid)
            status = str(result.get("status", "")).lower()
            if status in {"success", "succeeded", "done", "completed"}:
                return result
            if status in {"failed", "error", "timeout", "canceled", "cancelled"}:
                message = result.get("error_message") or result.get("message") or status
                raise RuntimeError(f"Yingdao job {job_uuid} ended with {status}: {message}")
            time.sleep(self.poll_interval_seconds)
        raise TimeoutError(f"Yingdao job {job_uuid} timed out after {timeout} seconds.")

    def extract_outputs(self, job_result: dict) -> dict:
        """Extract output fields from a Yingdao job result."""
        outputs = job_result.get("outputs") or job_result.get("output") or job_result.get("data") or {}
        if isinstance(outputs, list):
            mapped_outputs: dict[str, Any] = {}
            for item in outputs:
                if isinstance(item, dict) and "name" in item:
                    mapped_outputs[str(item["name"])] = item.get("value")
            outputs = mapped_outputs
        if not isinstance(outputs, dict):
            return {}

        return {
            "evidence_json_path": outputs.get("evidence_json_path")
            or outputs.get("search_evidence_json_path")
            or outputs.get("evidencePath"),
            "output_dir": outputs.get("output_dir") or outputs.get("outputDir"),
            **outputs,
        }
