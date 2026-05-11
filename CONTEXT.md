# XHS Automation Context

This file defines the shared language for Codex / agent work in this repository.

## Project identity

`xhs-automation` is the automation repository for Xiaohongshu content workflow development.

Current main architecture:

```text
Feishu / n8n
→ browser-worker
→ Provider Router
→ KuaJingVSOpenAPI
→ YingdaoService
→ Yingdao RPA UI Flow
→ evidence JSON
→ PostgreSQL / Feishu / Coze / OpenClaw
```

## Core terms

### browser-worker

Local FastAPI service. It receives `SearchJob` / `PublishJob`, validates schema, selects provider, dispatches RPA jobs, reads evidence files, returns `WorkerResult`, and later writes structured records.

### Provider Router

The routing layer that maps `provider_type` to an execution provider.

Allowed provider types:

- `kuaijingvs_yingdao_rpa`: main production-oriented path.
- `yingdao_rpa`: local Yingdao smoke / integration path.
- `selenium_chrome`: debug-only path.
- `manual`: human fallback path.

### KuaJingVSOpenAPI

Adapter for KuaJingVS / 跨境卫士 environment control. It opens, closes, lists, or checks account/shop browser environments. Page operations belong to the RPA flow, not this adapter.

### YingdaoService

Adapter for Yingdao / 影刀 OpenAPI. It starts jobs, polls status, verifies callbacks, and reads declared outputs. Unit tests must mock network calls.

### Yingdao RPA UI Flow

The page-action layer executed in the browser environment. It performs UI-level operations, screenshots, visible result extraction, and evidence file output.

If login, QR code, captcha, safety confirmation, account restriction, or any manual checkpoint appears, the flow must stop and return `waiting_human_verification`.

### evidence

Evidence means screenshots, JSON outputs, status logs, and structured artifacts proving what a workflow did. Evidence should be deterministic, inspectable, and suitable for PostgreSQL / MinIO / Feishu writeback.

### search_evidence.json

The standard search evidence file produced by the execution layer and consumed by browser-worker.

Expected fields:

- `job_id`
- `task_type`
- `status`
- `keyword`
- `account_id`
- `provider_type`
- `captured_at`
- `screenshot_path`
- `evidence_json_path`
- `item_count`
- `normalized_record_count`
- `result_area_found`
- `items`
- `normalized_records`

### publish_evidence.json

The standard publish evidence file produced by the execution layer and consumed by browser-worker.

Expected fields:

- `job_id`
- `task_type`
- `status`
- `account_id`
- `provider_type`
- `title`
- `image_count`
- `screenshots`
- `note_url`
- `error_code`
- `error_message`

### normalized_records

Canonical records derived from evidence for database and Feishu usage. For search records, keep stable fields such as:

- `job_id`
- `keyword`
- `account_id`
- `provider_type`
- `captured_at`
- `rank`
- `title`
- `author`
- `published_at_text`
- `note_id`
- `note_url`
- `metric_raw_text`
- `like_count_text`
- `screenshot_path`
- `evidence_json_path`

### waiting_human_verification

A safe stop state for checkpoints that require a person. The workflow must preserve screenshots, error code, and evidence for review.

### local replay

A deterministic local test path using fixture JSON, local files, and mocked providers. It should not touch external services unless a task explicitly says so.

### debug-only Selenium

`selenium_chrome` is retained for local debug, schema validation, screenshots, selector experiments, and backward-compatible tests. It is not the main production search or publish path.

## Ambiguities to resolve before coding

- "E2E" usually means local E2E replay unless explicitly stated otherwise.
- "发布" usually means simulated/local publish workflow unless explicitly approved for a real operation.
- "搜索" usually means evidence-producing search workflow, not uncontrolled crawling.
- "影刀调用" must distinguish mocked unit tests, local smoke tests, and real OpenAPI calls.
- "跨境卫士接入" must distinguish environment startup from page execution.

## Naming rules

- Use `xhs_*` for Xiaohongshu-specific Python modules, schemas, tables, and scripts.
- Use `*_evidence` for evidence builders and storage objects.
- Use `*_normalized_records` for canonical records intended for PostgreSQL / Feishu.
- Use `*_replay` for deterministic replay scripts.
- Use `*_smoke` only for smoke verification, not production workflows.
