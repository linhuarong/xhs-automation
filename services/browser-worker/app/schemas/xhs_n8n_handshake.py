from typing import Any, Literal

from pydantic import BaseModel, Field


XhsN8nHandshakeJobType = Literal["ping", "search", "publish", "full"]


class XhsN8nHandshakeRequest(BaseModel):
    """Request for controlled n8n webhook handshake smoke."""

    handshake_id: str
    job_id: str
    job_type: XhsN8nHandshakeJobType = "ping"
    account_id: str | None = None
    dry_run: bool = True
    webhook_url: str | None = None
    marker: str = "XHS_N8N_HANDSHAKE_SMOKE"
    payload: dict[str, Any] | None = None


class XhsN8nHandshakePayload(BaseModel):
    """Payload sent to a controlled n8n webhook handshake."""

    schema_version: str = "1.0"
    payload_type: str = "controlled_n8n_handshake_smoke_request"
    event: str
    handshake_id: str
    job_id: str
    job_type: XhsN8nHandshakeJobType
    account_id: str | None = None
    dry_run: bool = True
    marker: str = "XHS_N8N_HANDSHAKE_SMOKE"
    payload: dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)


class XhsN8nHandshakeResponse(BaseModel):
    """Sanitized response captured from a controlled n8n handshake."""

    schema_version: str = "1.0"
    response_type: str = "controlled_n8n_handshake_smoke_response"
    handshake_id: str
    job_id: str
    job_type: XhsN8nHandshakeJobType
    dry_run: bool = True
    http_status: int | None = None
    response_body: dict[str, Any] = Field(default_factory=dict)
    response_valid: bool = False
    marker_confirmed: bool = False
    external_call_made: bool = False
    error_code: str | None = None
    error_message: str | None = None


class XhsN8nHandshakeSummary(BaseModel):
    """Summary for controlled n8n webhook handshake smoke."""

    schema_version: str = "1.0"
    summary_type: str = "controlled_n8n_handshake_smoke_summary"
    handshake_id: str
    job_id: str
    job_type: XhsN8nHandshakeJobType
    dry_run: bool = True
    handshake_enabled: bool = False
    real_handshake_allowed: bool = False
    webhook_configured: bool = False
    webhook_url_redacted: str | None = None
    request_path: str | None = None
    response_path: str | None = None
    summary_path: str | None = None
    http_status: int | None = None
    response_valid: bool = False
    marker_confirmed: bool = False
    status: str
    sensitive_scan: dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: dict[str, bool] = Field(default_factory=dict)
    created_at: str
    error_code: str | None = None
    error_message: str | None = None
