import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import (
    YingdaoSmokePrepareResult,
    YingdaoSmokeReceipt,
    YingdaoSmokeRuntimeInfo,
    YingdaoSmokeSummary,
    YingdaoSmokeVerifyResult,
)
from app.services.yingdao_local_handoff_service import YingdaoLocalHandoffService
from app.utils.errors import (
    XHS_YINGDAO_DESKTOP_SMOKE_ERROR,
    XHS_YINGDAO_SMOKE_BROWSER_OPEN_FORBIDDEN,
    XHS_YINGDAO_SMOKE_EVIDENCE_INVALID,
    XHS_YINGDAO_SMOKE_EVIDENCE_NOT_FOUND,
    XHS_YINGDAO_SMOKE_RECEIPT_INVALID,
    XHS_YINGDAO_SMOKE_RECEIPT_NOT_FOUND,
    XHS_YINGDAO_SMOKE_XHS_OPEN_FORBIDDEN,
    WorkerError,
)


BROWSER_WORKER_ROOT = Path(__file__).resolve().parents[2]


class YingdaoDesktopSmokeService:
    """Manual Yingdao desktop smoke layer that only verifies local JSON files."""

    def __init__(
        self,
        handoff_service: YingdaoLocalHandoffService | None = None,
        queue_root: str | Path | None = None,
        worker_root: str | Path | None = None,
    ) -> None:
        """Create the desktop smoke service without starting Yingdao or browsers."""
        self.worker_root = Path(worker_root) if worker_root is not None else BROWSER_WORKER_ROOT
        self.handoff_service = handoff_service or YingdaoLocalHandoffService(
            queue_root=queue_root,
            worker_root=self.worker_root,
        )
        self.queue_root = self.handoff_service.queue_root

    def prepare_search_smoke(
        self,
        job_id: str,
        account_id: str,
        keyword: str,
        limit: int = 20,
    ) -> YingdaoSmokePrepareResult:
        """Prepare search active job and smoke directory for manual Yingdao desktop verification."""
        handoff = self.handoff_service.prepare_search_handoff(
            {
                "job_id": job_id,
                "account_id": account_id,
                "provider_type": "yingdao_local_file_trigger",
                "keyword": keyword,
                "limit": limit,
                "capture_screenshot": True,
            }
        )
        return self._prepare_smoke_result(
            job_type="xhs_search",
            job_id=job_id,
            active_job_path=handoff.active_job_path,
            expected_evidence_path=handoff.expected_evidence_path,
            message="Run Yingdao desktop RPA manually to read active job and write mock search evidence.",
        )

    def prepare_publish_smoke(
        self,
        job_id: str,
        account_id: str,
        title: str,
        body: str,
        tags: list[str],
        image_paths: list[str],
    ) -> YingdaoSmokePrepareResult:
        """Prepare publish active job and smoke directory for manual Yingdao desktop verification."""
        handoff = self.handoff_service.prepare_publish_handoff(
            {
                "job_id": job_id,
                "account_id": account_id,
                "provider_type": "yingdao_local_file_trigger",
                "title": title,
                "body": body,
                "tags": tags,
                "image_paths": image_paths,
                "publish_mode": "manual_review",
            }
        )
        return self._prepare_smoke_result(
            job_type="xhs_publish",
            job_id=job_id,
            active_job_path=handoff.active_job_path,
            expected_evidence_path=handoff.expected_evidence_path,
            message="Run Yingdao desktop RPA manually to read active publish job and write mock publish evidence.",
        )

    def get_smoke_paths(self, job_type: str, job_id: str) -> dict[str, str]:
        """Return all local paths for a smoke job."""
        normalized = self._normalize_job_type(job_type)
        category = self._category(normalized)
        smoke_dir = self.queue_root / "smoke" / category / job_id
        evidence_name = "search_evidence.json" if normalized == "xhs_search" else "publish_evidence.json"
        handoff_job_dir = self.queue_root / category / "jobs" / job_id
        active_name = "_active_job.json" if normalized == "xhs_search" else "_active_publish_job.json"
        active_path = self.queue_root / category / active_name
        return {
            "smoke_dir": str(smoke_dir),
            "active_job_path": str(active_path),
            "active_job_snapshot_path": str(smoke_dir / "active_job_snapshot.json"),
            "receipt_path": str(smoke_dir / "yingdao_smoke_receipt.json"),
            "evidence_path": str(handoff_job_dir / evidence_name),
            "smoke_evidence_path": str(smoke_dir / evidence_name),
            "summary_path": str(smoke_dir / "smoke_summary.json"),
        }

    def read_smoke_receipt(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read the smoke receipt JSON."""
        path = Path(self.get_smoke_paths(job_type, job_id)["receipt_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_SMOKE_RECEIPT_NOT_FOUND,
                f"Yingdao smoke receipt not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_SMOKE_RECEIPT_INVALID)

    def validate_smoke_receipt(self, receipt: dict[str, Any], job_type: str, job_id: str) -> dict[str, Any]:
        """Validate receipt safety flags and identity."""
        normalized = self._normalize_job_type(job_type)
        if not isinstance(receipt, dict):
            raise WorkerError(XHS_YINGDAO_SMOKE_RECEIPT_INVALID, "smoke receipt must be a JSON object")
        for field in ("job_id", "job_type", "status", "rpa_runtime"):
            if not receipt.get(field):
                raise WorkerError(XHS_YINGDAO_SMOKE_RECEIPT_INVALID, f"smoke receipt missing field: {field}")
        if receipt.get("job_id") != job_id or receipt.get("job_type") != normalized:
            raise WorkerError(XHS_YINGDAO_SMOKE_RECEIPT_INVALID, "smoke receipt job identity mismatch")
        runtime = receipt.get("rpa_runtime") or {}
        if runtime.get("opened_browser") is True:
            raise WorkerError(XHS_YINGDAO_SMOKE_BROWSER_OPEN_FORBIDDEN, "desktop smoke receipt says opened_browser=true")
        if runtime.get("opened_xhs") is True:
            raise WorkerError(XHS_YINGDAO_SMOKE_XHS_OPEN_FORBIDDEN, "desktop smoke receipt says opened_xhs=true")
        if runtime.get("called_external_api") is True:
            raise WorkerError(XHS_YINGDAO_SMOKE_RECEIPT_INVALID, "desktop smoke receipt says called_external_api=true")
        return receipt

    def read_smoke_evidence(self, job_type: str, job_id: str) -> dict[str, Any]:
        """Read the local smoke evidence JSON from the handoff evidence path."""
        path = Path(self.get_smoke_paths(job_type, job_id)["evidence_path"])
        if not path.exists():
            raise WorkerError(
                XHS_YINGDAO_SMOKE_EVIDENCE_NOT_FOUND,
                f"Yingdao smoke evidence not found: {path}",
            )
        return self._read_json(path, XHS_YINGDAO_SMOKE_EVIDENCE_INVALID)

    def validate_smoke_evidence(self, evidence: dict[str, Any], job_type: str, job_id: str) -> dict[str, Any]:
        """Validate local smoke evidence safety flags and identity."""
        normalized = self._normalize_job_type(job_type)
        if not isinstance(evidence, dict):
            raise WorkerError(XHS_YINGDAO_SMOKE_EVIDENCE_INVALID, "smoke evidence must be a JSON object")
        for field in ("job_id", "job_type", "status", "smoke_test"):
            if field not in evidence:
                raise WorkerError(XHS_YINGDAO_SMOKE_EVIDENCE_INVALID, f"smoke evidence missing field: {field}")
        if evidence.get("job_id") != job_id or evidence.get("job_type") != normalized:
            raise WorkerError(XHS_YINGDAO_SMOKE_EVIDENCE_INVALID, "smoke evidence job identity mismatch")
        smoke_test = evidence.get("smoke_test") or {}
        if smoke_test.get("opened_browser") is True:
            raise WorkerError(XHS_YINGDAO_SMOKE_BROWSER_OPEN_FORBIDDEN, "smoke evidence says opened_browser=true")
        if smoke_test.get("opened_xhs") is True:
            raise WorkerError(XHS_YINGDAO_SMOKE_XHS_OPEN_FORBIDDEN, "smoke evidence says opened_xhs=true")
        if normalized == "xhs_search" and smoke_test.get("real_search_executed") is True:
            raise WorkerError(XHS_YINGDAO_SMOKE_EVIDENCE_INVALID, "smoke evidence says real_search_executed=true")
        if normalized == "xhs_publish":
            if smoke_test.get("real_publish_executed") is True:
                raise WorkerError(XHS_YINGDAO_SMOKE_EVIDENCE_INVALID, "smoke evidence says real_publish_executed=true")
            if smoke_test.get("clicked_final_publish") is True:
                raise WorkerError(XHS_YINGDAO_SMOKE_EVIDENCE_INVALID, "smoke evidence says clicked_final_publish=true")
        return evidence

    def verify_smoke(self, job_type: str, job_id: str) -> YingdaoSmokeVerifyResult:
        """Verify receipt and evidence and write a local summary JSON."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_smoke_paths(normalized, job_id)
        summary = YingdaoSmokeSummary()
        receipt = None
        evidence = None
        status = "verified"
        error_code = None
        error_message = None
        message = "Yingdao desktop smoke verified"

        try:
            receipt = self.read_smoke_receipt(normalized, job_id)
            summary.receipt_exists = True
            self.validate_smoke_receipt(receipt, normalized, job_id)
            summary.receipt_valid = True
            runtime = receipt.get("rpa_runtime") or {}
            summary.opened_browser = bool(runtime.get("opened_browser", False))
            summary.opened_xhs = bool(runtime.get("opened_xhs", False))
        except WorkerError as exc:
            if exc.error_code == XHS_YINGDAO_SMOKE_RECEIPT_NOT_FOUND:
                status = "waiting_desktop_rpa"
                message = "Waiting for Yingdao desktop RPA to write smoke receipt"
            else:
                status = "failed"
                message = "Yingdao desktop smoke receipt invalid"
            error_code = exc.error_code
            error_message = exc.error_message

        if status != "failed":
            try:
                evidence = self.read_smoke_evidence(normalized, job_id)
                summary.evidence_exists = True
                self.validate_smoke_evidence(evidence, normalized, job_id)
                summary.evidence_valid = True
                smoke_test = evidence.get("smoke_test") or {}
                summary.opened_browser = summary.opened_browser or bool(smoke_test.get("opened_browser", False))
                summary.opened_xhs = summary.opened_xhs or bool(smoke_test.get("opened_xhs", False))
                summary.real_action_executed = self._real_action_executed(normalized, smoke_test)
            except WorkerError as exc:
                if exc.error_code == XHS_YINGDAO_SMOKE_EVIDENCE_NOT_FOUND and status != "waiting_desktop_rpa":
                    status = "waiting_desktop_rpa"
                    message = "Waiting for Yingdao desktop RPA to write mock evidence"
                elif exc.error_code != XHS_YINGDAO_SMOKE_EVIDENCE_NOT_FOUND:
                    status = "failed"
                    message = "Yingdao desktop smoke evidence invalid"
                if error_code is None or exc.error_code != XHS_YINGDAO_SMOKE_EVIDENCE_NOT_FOUND:
                    error_code = exc.error_code
                    error_message = exc.error_message

        result = YingdaoSmokeVerifyResult(
            job_id=job_id,
            job_type=normalized,
            status=status,
            receipt_path=paths["receipt_path"],
            evidence_path=paths["evidence_path"],
            smoke_summary_path=paths["summary_path"],
            summary=summary,
            receipt=receipt,
            evidence=evidence,
            message=message,
            error_code=error_code,
            error_message=error_message,
        )
        self.write_smoke_summary(self._model_to_dict(result))
        return result

    def write_mock_receipt_for_local_test(self, job_type: str, job_id: str) -> str:
        """Write a mock receipt for local tests only."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_smoke_paths(normalized, job_id)
        active_job = self._read_json(Path(paths["active_job_path"]), XHS_YINGDAO_DESKTOP_SMOKE_ERROR)
        receipt = YingdaoSmokeReceipt(
            job_type=normalized,
            job_id=job_id,
            account_id=str(active_job.get("account_id") or "xhs_dev_01"),
            provider_type=str(active_job.get("provider_type") or "yingdao_local_file_trigger"),
            read_at=self._utc_now(),
            source_active_job_path=paths["active_job_path"],
            evidence_output_dir=str(active_job.get("evidence_output_dir") or Path(paths["evidence_path"]).parent),
            rpa_runtime=YingdaoSmokeRuntimeInfo(),
        )
        return self._write_json(Path(paths["receipt_path"]), self._model_to_dict(receipt))

    def write_mock_evidence_for_local_test(self, job_type: str, job_id: str, status: str) -> str:
        """Write mock smoke evidence for local tests only."""
        normalized = self._normalize_job_type(job_type)
        paths = self.get_smoke_paths(normalized, job_id)
        active_job = self._read_json(Path(paths["active_job_path"]), XHS_YINGDAO_DESKTOP_SMOKE_ERROR)
        if normalized == "xhs_search":
            evidence = {
                "schema_version": "1.0",
                "job_id": job_id,
                "job_type": "xhs_search",
                "task_type": "xhs_keyword_search",
                "status": status,
                "keyword": active_job.get("keyword"),
                "account_id": active_job.get("account_id"),
                "provider_type": active_job.get("provider_type"),
                "captured_at": self._utc_now(),
                "screenshot_path": None,
                "item_count": 0,
                "normalized_record_count": 0,
                "result_area_found": False,
                "items": [],
                "normalized_records": [],
                "smoke_test": {
                    "desktop_rpa_read_active_job": True,
                    "opened_browser": False,
                    "opened_xhs": False,
                    "real_search_executed": False,
                },
            }
        else:
            evidence = {
                "schema_version": "1.0",
                "job_id": job_id,
                "job_type": "xhs_publish",
                "task_type": "xhs_content_publish",
                "status": status,
                "account_id": active_job.get("account_id"),
                "provider_type": active_job.get("provider_type"),
                "captured_at": self._utc_now(),
                "title": active_job.get("title"),
                "note_url": None,
                "screenshots": [],
                "screenshot_path": None,
                "message": "Yingdao desktop RPA smoke test wrote mock publish evidence. No browser opened. No publish executed.",
                "error_code": None,
                "error_message": None,
                "smoke_test": {
                    "desktop_rpa_read_active_job": True,
                    "opened_browser": False,
                    "opened_xhs": False,
                    "real_publish_executed": False,
                    "clicked_final_publish": False,
                },
            }
        path = self._write_json(Path(paths["evidence_path"]), evidence)
        self._write_json(Path(paths["smoke_evidence_path"]), evidence)
        return path

    def write_smoke_summary(self, summary: dict[str, Any]) -> str:
        """Write smoke verification summary to the smoke directory."""
        paths = self.get_smoke_paths(str(summary["job_type"]), str(summary["job_id"]))
        return self._write_json(Path(paths["summary_path"]), summary)

    def _prepare_smoke_result(
        self,
        job_type: str,
        job_id: str,
        active_job_path: str,
        expected_evidence_path: str,
        message: str,
    ) -> YingdaoSmokePrepareResult:
        paths = self.get_smoke_paths(job_type, job_id)
        smoke_dir = Path(paths["smoke_dir"])
        smoke_dir.mkdir(parents=True, exist_ok=True)
        active_payload = self._read_json(Path(active_job_path), XHS_YINGDAO_DESKTOP_SMOKE_ERROR)
        snapshot_path = self._write_json(Path(paths["active_job_snapshot_path"]), active_payload)
        return YingdaoSmokePrepareResult(
            job_id=job_id,
            job_type=self._normalize_job_type(job_type),
            status="waiting_desktop_rpa",
            active_job_path=active_job_path,
            smoke_dir=str(smoke_dir),
            expected_receipt_path=paths["receipt_path"],
            expected_evidence_path=expected_evidence_path,
            active_job_snapshot_path=snapshot_path,
            message=message,
        )

    def _read_json(self, path: Path, error_code: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkerError(error_code, f"JSON file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkerError(error_code, f"JSON file invalid: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise WorkerError(error_code, f"JSON file must contain an object: {path}")
        return payload

    def _write_json(self, path: Path, payload: dict[str, Any]) -> str:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
        except OSError as exc:
            raise WorkerError(
                XHS_YINGDAO_DESKTOP_SMOKE_ERROR,
                f"failed to write Yingdao desktop smoke JSON: {path}: {exc}",
            ) from exc

    def _normalize_job_type(self, job_type: str) -> str:
        normalized = str(job_type or "").strip().lower()
        if normalized in {"search", "xhs_search"}:
            return "xhs_search"
        if normalized in {"publish", "xhs_publish"}:
            return "xhs_publish"
        raise WorkerError(XHS_YINGDAO_DESKTOP_SMOKE_ERROR, f"unsupported smoke job_type: {job_type}")

    def _category(self, job_type: str) -> str:
        return "search" if self._normalize_job_type(job_type) == "xhs_search" else "publish"

    def _real_action_executed(self, job_type: str, smoke_test: dict[str, Any]) -> bool:
        if job_type == "xhs_search":
            return bool(smoke_test.get("real_search_executed", False))
        return bool(smoke_test.get("real_publish_executed", False) or smoke_test.get("clicked_final_publish", False))

    def _model_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
