# xhs-browser-worker

FastAPI skeleton for the browser-worker service.

This service currently provides the FastAPI shell, health check, schemas, local evidence handling, optional PostgreSQL writes, and a local development Chrome debug provider.

The project architecture has moved to the RPA V2 design:

- KuaJingVS / 跨境卫士 starts the account or shop browser environment.
- Yingdao / 影刀 RPA executes the XHS page UI Flow.
- browser-worker acts as the RPA scheduler and evidence receiver.
- PostgreSQL, Feishu hotspot pool, and Coze/Dify consume `normalized_records`.
- `selenium_chrome_provider` is retained only for local debug.
- Direct search URL is debug-only and should not be treated as the main production path.

## Local Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Start

Run the service from this directory:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Health Check

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "xhs-browser-worker",
  "version": "0.1.0"
}
```

## API Smoke Test

Start the service first. The smoke test script only checks the already-running local service and does not start Uvicorn.

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another PowerShell window, run:

```powershell
.\scripts\smoke_test.ps1
```

The script checks:

- `GET /health`
- `POST /api/xhs/search`
- `POST /api/xhs/publish`
- `GET /api/xhs/publish/publish-smoke-1`

Expected final output:

```text
browser-worker smoke test passed
```

## RPA V2 Main Path

The intended main path for `/api/xhs/search` and `/api/xhs/publish` is:

```text
browser-worker
-> Provider Router
-> KuaJingVS environment start
-> Yingdao RPA UI Flow
-> search_evidence.json / publish_evidence.json
-> browser-worker reads evidence
-> WorkerResult
-> PostgreSQL / Feishu / Coze
```

Current `provider_type` values:

- `selenium_chrome`: local debug-only.
- `yingdao_rpa`: directly dispatch Yingdao RPA and read evidence.
- `kuaijingvs_yingdao_rpa`: open KuaJingVS environment, wait until ready, dispatch Yingdao RPA, then read evidence.
- `kuaijingvs_local_file_trigger`: open KuaJingVS environment, write a local pending job JSON for Yingdao file trigger, then wait for evidence.
- `manual`: reserved.

`YingdaoService` should own token/config loading, starting an RPA job, querying job status, waiting for completion, and returning output paths. The Yingdao app must output `search_evidence.json` for search jobs. PostgreSQL should read evidence JSON / `normalized_records`, not depend on Selenium `items`.

Task 24A adds the provider router and Yingdao RPA evidence reader:

- `get_provider("selenium_chrome")` returns the local debug provider.
- `get_provider("yingdao_rpa")` returns `YingdaoRpaProvider`.
- `get_provider("kuaijingvs_yingdao_rpa")` returns `KuaJingVSYingdaoRpaProvider`.
- Unknown provider types raise a clear provider error.
- Unit tests mock Yingdao calls and do not access real Yingdao, XHS, or Chrome.

Yingdao configuration is read from environment variables:

```powershell
$env:YINGDAO_API_BASE_URL = "https://api.winrobot360.com"
$env:YINGDAO_ACCESS_KEY_ID = "change_me"
$env:YINGDAO_ACCESS_KEY_SECRET = "change_me"
$env:YINGDAO_ACCOUNT_NAME = "change_me"
$env:YINGDAO_ROBOT_UUID = "change_me"
$env:YINGDAO_JOB_POLL_INTERVAL_SECONDS = "3"
$env:YINGDAO_JOB_TIMEOUT_SECONDS = "600"
```

Manual smoke evidence can be placed under:

```text
.local_evidence/yingdao-smoke-1/search_evidence.json
```

The RPA evidence reader maps `screenshot_path` to `screenshot_url`, preserves UTF-8 Chinese fields, and returns `items` plus `normalized_records`.

Task 24B hardens the Yingdao service contract:

- Missing `YINGDAO_ACCESS_KEY_ID`, `YINGDAO_ACCESS_KEY_SECRET`, `YINGDAO_ACCOUNT_NAME`, or `YINGDAO_ROBOT_UUID` fails before a real job start.
- Invalid poll interval or timeout values return explicit configuration errors.
- `wait_job_done` maps RPA failure and timeout to structured errors.
- `extract_outputs` accepts common evidence fields such as `evidence_json_path`, `evidence_output_dir`, `output_dir`, `search_evidence_json`, `search_evidence_path`, `screenshot_path`, and `status`.

Task 24C adds a mockable KuaJingVS service skeleton:

- `KuaJingVSService` reads account/profile mapping from `KJVS_PROFILE_MAP_PATH`.
- It defines `list_shops`, `resolve_shop_id`, `open_shop`, `close_shop`, and `wait_environment_ready`.
- Unit tests mock all HTTP calls and do not access a real KuaJingVS process at `127.0.0.1:49709`.
- Task 24D wires Provider Router to `KuaJingVSYingdaoRpaProvider`, which calls `resolve_shop_id`, `open_shop`, `wait_environment_ready`, then delegates to `YingdaoRpaProvider.search`.
- Task 24D remains mock-tested composition code. Real local integration still requires KuaJingVS, a Yingdao app, `KJVS_PROFILE_MAP_PATH`, `YINGDAO_ROBOT_UUID`, and valid local credentials/config.
- If XHS shows QR code, captcha, safety confirmation, or risk control, the flow must return `waiting_human_verification`; the worker does not automate those checks.

KuaJingVS configuration is read from environment variables:

```powershell
$env:KJVS_API_BASE_URL = "http://127.0.0.1:49709"
$env:KJVS_API_ID = "change_me"
$env:KJVS_API_SECRET = "change_me"
$env:KJVS_PROFILE_MAP_PATH = ".config/kuaijingvs_profiles.json"
$env:KJVS_ENV_READY_TIMEOUT_SECONDS = "60"
$env:KJVS_ENV_POLL_INTERVAL_SECONDS = "3"
$env:RPA_LOCAL_QUEUE_ROOT = ".local_rpa_jobs"
$env:RPA_LOCAL_EVIDENCE_ROOT = ".local_evidence"
$env:RPA_LOCAL_EVIDENCE_TIMEOUT_SECONDS = "300"
$env:RPA_WRITE_EVIDENCE_SCRIPT_PATH = "scripts/write_yingdao_smoke_evidence.ps1"
```

## Local File Trigger RPA

Task 24H adds `provider_type = kuaijingvs_local_file_trigger` for local Yingdao personal-edition workflows that cannot reliably use Yingdao OpenAPI. The worker still uses KuaJingVS for the account environment, but triggers Yingdao by writing a local file that a Yingdao file trigger watches.

Flow:

```text
/api/xhs/search
-> Provider Router
-> KuaJingVSLocalFileTriggerProvider
-> KuaJingVS resolve/open/wait ready
-> write .local_rpa_jobs/pending/_active_job.json
-> write .local_rpa_jobs/pending/_trigger_{job_id}.trigger
-> Yingdao file trigger sees the trigger marker
-> Yingdao writes .local_evidence/{job_id}/search_evidence.json
-> browser-worker reads evidence and returns WorkerResult
```

The local queue directories are:

```text
.local_rpa_jobs/
  pending/
  processing/
  done/
  failed/
```

Yingdao file trigger should watch:

```text
.local_rpa_jobs/pending
```

Trigger settings:

- File type: `*.trigger`
- Event: create
- First step in Yingdao reads the fixed file:
  `G:\AI-Automation\xhs-automation\services\browser-worker\.local_rpa_jobs\pending\_active_job.json`

The worker writes `_active_job.json` first, then writes `_trigger_{job_id}.trigger`. The trigger file can contain only the `job_id`; the active job file contains the full payload. The old `pending/{job_id}.json` format is no longer written to avoid accidental trigger mismatch.

Pending search job JSON includes:

- `job_id`
- `task_type = xhs_keyword_search`
- `account_id`
- `provider_type = kuaijingvs_local_file_trigger`
- `keyword`
- `limit`
- `output_dir`
- `before_scroll_screenshot_path`
- `expected_evidence_json_path`
- `expected_screenshot_path`
- `dos_command`
- `created_at`

Yingdao should write:

```text
.local_evidence/{job_id}/xhs_search_before_scroll.png
.local_evidence/{job_id}/xhs_search_smoke.png
.local_evidence/{job_id}/search_evidence.json
```

This mode does not bypass QR code, captcha, safety verification, or risk control. If manual handling is required, Yingdao should write evidence with `status = waiting_human_verification`. The first version is single-job oriented; queue processing order is controlled by the Yingdao file trigger setup.

Concurrency note: this fixed active-job file mode is single-machine, single-job serial only. Do not run concurrent local file trigger jobs, because each new job overwrites `_active_job.json`.

## RPA Dry-Run

Task 24E adds a local dry-run check before real KuaJingVS and Yingdao integration. It validates local config, profile map readability, account mapping, Yingdao account/robot settings, and evidence output paths. It does not call Yingdao, does not call KuaJingVS, does not open Chrome, and does not visit XHS.

Run from `services/browser-worker`:

```powershell
.\scripts\rpa_dry_run.ps1 `
  -JobId "dry-run-1" `
  -AccountId "xhs_dev_01" `
  -Keyword "眼影" `
  -ProviderType "kuaijingvs_yingdao_rpa"
```

Expected report shape:

```json
{
  "job_id": "dry-run-1",
  "provider_type": "kuaijingvs_yingdao_rpa",
  "account_id": "xhs_dev_01",
  "keyword": "眼影",
  "status": "success",
  "checks": [],
  "resolved": {
    "shop_id": "123456",
    "evidence_output_dir": ".local_evidence/dry-run-1",
    "expected_evidence_json_path": ".local_evidence/dry-run-1/search_evidence.json",
    "expected_screenshot_path": ".local_evidence/dry-run-1/xhs_search_smoke.png"
  },
  "error_code": null,
  "error_message": null
}
```

Profile map example only; do not commit real account data:

```json
{
  "xhs_dev_01": {
    "shop_id": "123456",
    "shop_name": "小红书测试账号01",
    "provider_type": "kuaijingvs_yingdao_rpa"
  }
}
```

Before a real local integration run, prepare `KJVS_PROFILE_MAP_PATH`, `YINGDAO_ACCOUNT_NAME`, `YINGDAO_ROBOT_UUID`, a Yingdao app that writes `search_evidence.json`, and matching `evidence_output_dir` behavior. QR code, captcha, safety confirmation, and risk-control prompts still require human handling; the worker must not automate those checks.

## Legacy XHS Search Debug Prototype

`POST /api/xhs/search` currently still contains a minimal real-browser debug prototype through the local Selenium Chrome provider. It opens the XHS search page with an encoded `keyword` query parameter, types the keyword into a visible search input, presses Enter, saves a local screenshot, and returns a `WorkerResult`.

This prototype is legacy debug-only and only for low-frequency manual validation:

- It uses a real browser page and does not call unauthorized XHS APIs.
- It does not reverse engineer requests, fake XHR/fetch, or bypass login, captcha, QR code, risk control, or second-factor checks.
- First run may require a human to log in in the local Chrome profile.
- If a visible login, captcha, verification, or risk control prompt appears, the job returns `waiting_human_verification`.
- The worker checks visible page text and explicit prompt elements; it does not classify a page as waiting only because the HTML source contains generic login text.
- Chinese keyword requests should be sent as UTF-8 JSON bytes.
- If the search input contains `undefined`, `??`, an empty value, or a value different from `SearchJob.keyword`, the worker corrects it using only native Selenium element methods: `click`, `clear`, and `send_keys`.
- If input still fails, check the local `search_error` screenshot and the `input_keyword` structured log first.
- The waiting screenshot is saved locally as `search_waiting_human.png`.
- After the human completes the browser prompt in the Chrome profile, call `/api/xhs/search` again with the same account profile to retry.
- If the page still requires manual action, the job returns `waiting_human_verification` again.
- A successful low-frequency manual run saves `search_success.png` locally.
- After a successful search, it tries to extract the first `SearchJob.limit` visible result cards.
- Result extraction only reads the current visible DOM and does not open detail pages or scroll to load more.
- Extracted fields include `rank`, `title`, `author`, `note_url`, and `visible_metrics` when they are visible on the page.
- Returned `items` are cleaned and filtered before ranking: `title` and `author` are whitespace-normalized, `visible_metrics` defaults to `{}`, and invalid cards are removed.
- `note_url` is the key validity signal for a note item. It must point to an XHS `/explore/...` or `/search_result/...` path; home pages, bare search pages, empty links, and non-XHS links are filtered out.
- Some fields may be empty until selectors are calibrated against the live page.
- More precise `title` and `author` extraction should be handled by a later selector calibration task.
- Successful searches write a local structured evidence file under `.local_evidence/{job_id}/search_evidence.json`.
- The API returns this path as `evidence_json_path`; `screenshot_url` and `items` remain unchanged.
- The evidence JSON includes job metadata, keyword, account, provider, UTC capture time, search URL, screenshot path, result-area status, item count, and cleaned items.
- Evidence JSON also includes `normalized_records`, which is the standard record structure intended for later PostgreSQL and Feishu hotspot-field mapping.
- `items` remains the cleaned page extraction result. `normalized_records` is the pre-database/pre-writeback structure.
- In `normalized_records`, `author` text is split into `author` and `published_at_text`, `note_url` is parsed into `note_id`, and `visible_metrics` is normalized into `metric_raw_text` and `like_count_text`.
- Local evidence files are for development validation only.
- It does not upload screenshots to MinIO and does not write Feishu.
- The RPA main path should produce the same evidence JSON structure from the Yingdao app.

Manual request example after starting the service:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/xhs/search `
  -ContentType "application/json" `
  -Body '{"job_id":"search-manual-1","account_id":"xhs_dev_01","keyword":"眼影"}'
```

For Chinese keywords in PowerShell, send UTF-8 JSON bytes:

```powershell
$body = '{"job_id":"search-evidence-1","account_id":"xhs_dev_01","keyword":"眼影","limit":5}'
$result = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/xhs/search `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

PowerShell console rendering may still display Chinese objects incorrectly. To inspect the response, write it to UTF-8 JSON:

```powershell
$result | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 search_result_check.json
```

## Open Local Chrome Profile

Use `scripts/open_profile.ps1` to open the local Chrome profile for a specific `account_id` during manual development checks. The script creates the profile directory under `.local_profiles/{account_id}` and opens Chrome with `--user-data-dir` pointing to that directory.

Open the default XHS home page:

```powershell
.\scripts\open_profile.ps1 xhs_dev_01
```

Open a specific URL, such as Chrome version details:

```powershell
.\scripts\open_profile.ps1 xhs_dev_01 -Url "chrome://version"
```

If Chrome is installed in a non-standard location, pass the executable path:

```powershell
.\scripts\open_profile.ps1 xhs_dev_01 -ChromePath "C:\Path\To\chrome.exe"
```

In `chrome://version`, confirm that `Profile Path` points to `services\browser-worker\.local_profiles\xhs_dev_01\Default` or the matching Chrome profile path under that user data directory.

## Pytest

Install dependencies, then run tests from the `services/browser-worker` directory:

```powershell
pip install -r requirements.txt
pytest
```

The pytest suite covers the health endpoint, schema defaults, `WorkerResult`, and the in-memory job registry. It does not start Chrome, execute Selenium, visit XHS, or call external services.

## Image Download Service

`download_images(job_id, image_urls, download_root=".local_downloads")` downloads HTTP/HTTPS image URLs into a local job directory:

```text
{download_root}/{job_id}/
```

Files are named with a stable sequence prefix, such as `001_image.png`. If a URL has no filename, the downloader uses `001_image`.

Example:

```powershell
python -c "from app.services.image_downloader import download_images; print(download_images('manual-test', ['https://example.com/image.png']))"
```

Local downloads are ignored by Git under `.local_downloads/`. This service does not upload to MinIO or call Feishu/PostgreSQL.

## Browser Utility Layer

The browser-worker includes small browser utility helpers that operate only on caller-provided driver or element objects:

- `save_screenshot(driver, job_id, name)` saves `{screenshot_root}/{job_id}/{name}.png` locally and does not upload to MinIO.
- `upload_files_to_input(file_input, file_paths)` validates local paths and sends newline-joined paths to a file input via `send_keys`.
- `clear_and_type(element, text)` clears an element and types text via `send_keys`.
- `safe_type(element, text)` uses `clear + send_keys` when available, with a `click + send_keys` fallback.

These helpers do not open websites, use the clipboard, operate OS file picker dialogs, or make network requests.

## Local Chrome Provider Smoke Test

The Selenium Chrome provider is only for local development debugging. It starts a normal local Chrome profile, does not open XHS by default, and does not visit any external website.

Run this from the `services/browser-worker` directory after installing dependencies:

```powershell
python -c "from app.providers import SeleniumChromeProvider; provider = SeleniumChromeProvider(); session = provider.open_profile('local-dev'); print(session); print(provider.check_login(provider.get_driver(session))); provider.close_profile(session)"
```

To capture a local screenshot of the initial Chrome window:

```powershell
python -c "from app.providers import SeleniumChromeProvider; provider = SeleniumChromeProvider(); session = provider.open_profile('local-dev'); print(provider.capture_screenshot(session, 'smoke')); provider.close_profile(session)"
```

Local Chrome profile data is written under `.local_profiles/{account_id}` by default. Local screenshots are written under `.local_screenshots/{session_id}/{name}.png` by default.

## XHS Keyword Search Module

The browser-worker keyword search path accepts `SearchJob` payloads, routes by `provider_type`, waits for provider evidence, normalizes XHS result items, and returns `WorkerResult` data for later Feishu/PostgreSQL/MinIO integration.

Supported provider types:

- `selenium_chrome`: local debug only.
- `yingdao_rpa`: Yingdao RPA provider skeleton.
- `kuaijingvs_yingdao_rpa`: KuaJingVS open-shop plus Yingdao RPA skeleton.
- `kuaijingvs_local_file_trigger`: KuaJingVS open-shop plus local file trigger handoff.
- `manual`: reserved, not implemented.

For `kuaijingvs_local_file_trigger`, the execution flow is:

1. Resolve `account_id` to `shop_id`.
2. Call KuaJingVS `open_shop`.
3. Create `.local_evidence/{job_id}`.
4. Write `.local_rpa_jobs/pending/_active_job.json`.
5. Write `.local_rpa_jobs/pending/_trigger_{job_id}.trigger`.
6. Wait for `.local_evidence/{job_id}/search_evidence.json`.
7. Read and return evidence.

The active job file contains the current payload for Yingdao, and the trigger marker is the file-system event used by the local RPA flow. The provider does not require WebDriver or Chrome devtools readiness before writing these files.

Evidence directory layout:

```text
.local_evidence/{job_id}/
  search_evidence.json
  xhs_search_smoke.png
  xhs_search_before_scroll.png
```

`search_evidence.json` may include:

- `job_id`, `task_type`, `status`, `keyword`, `account_id`, `provider_type`
- `captured_at`, `screenshot_path`, `evidence_json_path`
- `result_area_found`, `item_count`, `normalized_record_count`
- `items[]`: raw visible XHS search items
- `normalized_records[]`: standardized records for downstream storage
- `error_code`, `error_message`

Normalize an evidence file:

```powershell
.\scripts\xhs_normalize_evidence.ps1 -EvidenceJsonPath ".local_evidence\job-1\search_evidence.json" -WriteBack
```

Or call the API:

```http
POST /api/xhs/search/normalize
{
  "evidence_json_path": ".local_evidence/job-1/search_evidence.json",
  "write_back": true
}
```

Run a synchronous keyword batch through browser-worker:

```http
POST /api/xhs/keywords/batch
{
  "batch_id": "xhs-batch-001",
  "account_id": "xhs_dev_01",
  "provider_type": "kuaijingvs_local_file_trigger",
  "keywords": ["眼影", "粉底液", "睫毛膏"],
  "limit": 20,
  "mode": "sync"
}
```

PowerShell helper:

```powershell
.\scripts\xhs_batch_keywords.ps1 -BatchId "xhs-batch-001" -AccountId "xhs_dev_01" -ProviderType "kuaijingvs_local_file_trigger" -Keywords "眼影,粉底液,睫毛膏" -Limit 20
```

Current storage, Feishu, and PostgreSQL boundaries are local mocks or in-memory adapters. Real Yingdao, XHS, KuaJingVS, Feishu, PostgreSQL, and MinIO integration is left for final closed-loop acceptance.

## XHS Publish Flow

The publish path is code-complete for local orchestration only. It does not publish to XHS, call real Yingdao, call real KuaJingVS during tests, or upload to Feishu/PostgreSQL/MinIO.

Publish job payload:

```json
{
  "job_id": "publish-001",
  "account_id": "xhs_dev_01",
  "provider_type": "kuaijingvs_local_file_trigger_publish",
  "title": "新品眼影试色",
  "body": "正文内容",
  "tags": ["眼影", "彩妆"],
  "assets": [
    {
      "local_path": "G:\\images\\001.png",
      "order": 1,
      "asset_type": "image"
    }
  ]
}
```

Publish evidence fields:

- `job_id`, `task_type`, `status`, `account_id`, `provider_type`, `title`
- `note_url`, `note_id`, `published_at`
- `evidence_json_path`, `screenshot_path`
- `before_publish_screenshot_path`, `form_filled_screenshot_path`, `result_screenshot_path`
- `error_code`, `error_message`, `raw`

For `kuaijingvs_local_file_trigger_publish`, the execution flow is:

1. Resolve `account_id` to `shop_id`.
2. Call KuaJingVS `open_shop`.
3. Create `.local_evidence/{job_id}`.
4. Write `.local_rpa_jobs/pending/_active_publish_job.json`.
5. Write `.local_rpa_jobs/pending/_trigger_publish_{job_id}.trigger`.
6. Wait for `.local_evidence/{job_id}/publish_evidence.json`.
7. Read evidence and map it to `XhsPublishResult`.

The publish trigger provider does not require WebDriver or Chrome devtools readiness before writing the trigger.

Single publish API:

```http
POST /api/xhs/publish
```

Batch publish API:

```http
POST /api/xhs/publish/batch
```

PowerShell helpers:

```powershell
.\scripts\xhs_publish_note.ps1 -JobId "publish-001" -AccountId "xhs_dev_01" -ProviderType "kuaijingvs_local_file_trigger_publish" -Title "标题" -Body "正文" -Tags "眼影,彩妆" -AssetPaths "G:\images\001.png"
.\scripts\xhs_batch_publish.ps1 -BatchId "publish-batch-001" -AccountId "xhs_dev_01" -ProviderType "kuaijingvs_local_file_trigger_publish" -JobsJsonPath ".\publish_jobs.json"
```

Real publish acceptance remains a later closed-loop task: real XHS UI flow, real Yingdao app execution, real KuaJingVS environment validation, Feishu status writeback, PostgreSQL persistence, and MinIO upload.

## XHS Automation Workflow

The local code-level workflow now covers search, evidence normalization, publish, mock archive, mock Feishu, mock PostgreSQL, n8n webhook contracts, OpenClaw job status, audit JSONL, and in-memory job registry. All external integrations remain in mock/local mode until real acceptance.

Search chain:

```text
API / n8n webhook
-> keyword batch
-> provider router
-> local file trigger or mock provider
-> search_evidence.json
-> normalized_records
-> mock archive / mock adapter boundaries
```

Publish chain:

```text
API / n8n webhook
-> publish batch
-> provider router
-> _active_publish_job.json + _trigger_publish_{job_id}.trigger
-> publish_evidence.json
-> mock archive / mock adapter boundaries
```

n8n webhook contracts:

```http
POST /api/webhooks/n8n/xhs/search
POST /api/webhooks/n8n/xhs/publish
```

OpenClaw job status contract:

```http
POST /api/webhooks/openclaw/xhs/job-status
{
  "job_id": "xxx",
  "job_type": "search"
}
```

Workflow health:

```http
GET /api/workflows/xhs/health
```

Mock E2E workflow:

```http
POST /api/xhs/workflows/search-to-publish/mock
{
  "workflow_id": "wf-local-001",
  "account_id": "xhs_dev_01",
  "keywords": ["眼影", "粉底液"],
  "limit": 20,
  "max_publish_jobs": 1,
  "mode": "mock"
}
```

PowerShell helpers:

```powershell
.\scripts\xhs_health_check.ps1
.\scripts\xhs_job_status.ps1 -JobId "job-1" -JobType "search"
.\scripts\xhs_e2e_mock.ps1 -WorkflowId "wf-local-001" -AccountId "xhs_dev_01" -Keywords "眼影,粉底液" -Limit 20 -MaxPublishJobs 1
```

Local file trigger working mode:

- Search active job: `.local_rpa_jobs/pending/_active_job.json`
- Search trigger: `.local_rpa_jobs/pending/_trigger_{job_id}.trigger`
- Publish active job: `.local_rpa_jobs/pending/_active_publish_job.json`
- Publish trigger: `.local_rpa_jobs/pending/_trigger_publish_{job_id}.trigger`
- Search evidence: `.local_evidence/{job_id}/search_evidence.json`
- Publish evidence: `.local_evidence/{job_id}/publish_evidence.json`
- Audit log: `.local_logs/xhs_audit.jsonl`

Final real integration acceptance checklist:

Search acceptance:

- Confirm KuaJingVS OpenAPI host and port.
- Confirm profile map account-to-shop mapping.
- Confirm Yingdao file trigger listens to `*.trigger`.
- Confirm Yingdao reads `_active_job.json`.
- Run XHS search UI flow in the real browser environment.
- Produce `xhs_search_before_scroll.png`.
- Produce `xhs_search_smoke.png`.
- Produce `search_evidence.json`.
- Confirm API returns `success`.

Publish acceptance:

- Confirm Yingdao publish trigger listens to publish trigger files.
- Confirm Yingdao reads `_active_publish_job.json`.
- Upload images through real UI flow.
- Fill title, body, and tags.
- Produce publish-before screenshot.
- Produce form-filled screenshot.
- Produce publish-result screenshot.
- Produce `publish_evidence.json`.
- Confirm API returns `success` or `waiting_human_verification`.

External system acceptance:

- Map Feishu base fields.
- Add PostgreSQL migrations.
- Configure MinIO bucket and object-key rules.
- Build n8n workflow.
- Wire OpenClaw notification/status flow.

## External Readiness

Task 28 adds a pre-integration readiness layer for real system handoff. It only checks local configuration contracts, env placeholders, profile-map shape, local webhook routes, and safe-mode flags.

It does not:

- Visit XHS.
- Search XHS.
- Publish to XHS.
- Start Yingdao tasks.
- Open KuaJingVS shops.
- Write Feishu.
- Write PostgreSQL.
- Upload MinIO objects.

Readiness defaults:

- `safe_mode = true`
- `XHS_EXTERNAL_READINESS_MODE = dry_run`
- `XHS_ALLOW_LIVE_READONLY_CHECKS = false`
- `XHS_ALLOW_LIVE_WRITE_ACTIONS = false`

Live readonly checks must be explicitly enabled in a later task. Live write actions should never be executed by readiness checks.

API:

```http
GET /api/workflows/xhs/external-readiness
```

PowerShell:

```powershell
.\scripts\xhs_external_readiness.ps1 -BaseUrl "http://127.0.0.1:8000"
```

Dependency status meanings:

- `missing_config`: required config placeholder is absent or still `change_me`.
- `mock_ready`: local mock adapter or local API contract is available.
- `ready`: dry-run config and local files are present enough for the next manual readonly step.
- `failed`: local config exists but is invalid, such as malformed profile-map JSON.
- `disabled`: dependency is intentionally off.

KuaJingVS profile map example:

```json
{
  "xhs_dev_01": {
    "shop_id": "change_me",
    "shop_name": "小红书测试账号01",
    "provider_type": "kuaijingvs_yingdao_rpa"
  }
}
```

Validate the profile map locally:

```powershell
.\scripts\xhs_validate_profile_map.ps1 -ProfileMapPath ".config\kuaijingvs_profiles.json"
```

Allowed profile-map provider types:

- `kuaijingvs_yingdao_rpa`
- `yingdao_rpa`
- `manual`
- `selenium_chrome_debug`

The readiness API writes a local audit event with `event_type = external_readiness_check`. It records only booleans and summary counts, never secret values.

## KuaJingVS Live Readonly Discovery

Task 29 adds the first live-readonly discovery step for KuaJingVS. It is strictly limited to read-only local OpenAPI discovery and profile-map matching.

It can only call:

- `GET /v1/shops?page=1&size=50`

It must not:

- Call `POST /v1/shops/{shop_id}/open`.
- Call `POST /v1/shops/{shop_id}/close`.
- Open a browser.
- Open XHS.
- Search XHS.
- Publish to XHS.
- Start Yingdao.
- Write Feishu, PostgreSQL, or MinIO.

Live readonly is disabled by default. To enable it for a manual local discovery run:

```powershell
$env:XHS_ALLOW_LIVE_READONLY_CHECKS = "true"
$env:XHS_ALLOW_LIVE_WRITE_ACTIONS = "false"
$env:KJVS_API_BASE_URL = "http://127.0.0.1:49709"
$env:KJVS_PROFILE_MAP_PATH = ".config/kuaijingvs_profiles.json"
```

Restart browser-worker after changing environment variables.

Profile map:

```json
{
  "xhs_dev_01": {
    "shop_id": "123456",
    "shop_name": "小红书测试账号01",
    "provider_type": "kuaijingvs_yingdao_rpa"
  }
}
```

Validate the profile map before discovery:

```powershell
.\scripts\xhs_validate_profile_map.ps1 -ProfileMapPath ".config\kuaijingvs_profiles.json"
```

Run discovery through browser-worker:

```powershell
.\scripts\xhs_kjvs_discovery.ps1 -BaseUrl "http://127.0.0.1:8000"
```

Discovery evidence is saved locally:

```text
.local_evidence/kuaijingvs_discovery/discovery.json
```

Readiness will not trigger discovery. It only reports whether prior discovery evidence exists:

```powershell
.\scripts\xhs_external_readiness.ps1 -BaseUrl "http://127.0.0.1:8000"
```

Common discovery statuses:

- `live readonly disabled`: set `XHS_ALLOW_LIVE_READONLY_CHECKS=true` and restart browser-worker.
- `api base url missing`: set `KJVS_API_BASE_URL`.
- `profile map missing`: create `.config/kuaijingvs_profiles.json`.
- `profile map invalid`: fix JSON or required fields.
- `shop unmatched`: profile map `shop_id` did not appear in discovered shops; this is a warning for manual correction.
- `KuaJingVS API timeout`: confirm KuaJingVS local OpenAPI is running and the port is correct.

Manual acceptance sequence:

```powershell
cd services/browser-worker
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```powershell
.\scripts\xhs_external_readiness.ps1 -BaseUrl "http://127.0.0.1:8000"
.\scripts\xhs_validate_profile_map.ps1 -ProfileMapPath ".config\kuaijingvs_profiles.json"
```

Then enable live readonly, restart browser-worker, and run:

```powershell
.\scripts\xhs_kjvs_discovery.ps1 -BaseUrl "http://127.0.0.1:8000"
```

Only the last command is allowed to contact KuaJingVS local readonly API, and it still must not open or close any shop environment.

## Yingdao Local File Trigger Contract

Task 30 adds the local file handoff contract between browser-worker and the future Yingdao desktop RPA flow. It only writes and reads local JSON files. It does not start Yingdao, open KuaJingVS, open Chrome, visit XHS, search XHS, or click publish.

Local handoff directory:

```text
.local_rpa_queue/
  yingdao/
    search/
      _active_job.json
      jobs/{job_id}/job.json
      jobs/{job_id}/handoff_manifest.json
      jobs/{job_id}/search_evidence.json
    publish/
      _active_publish_job.json
      jobs/{job_id}/job.json
      jobs/{job_id}/handoff_manifest.json
      jobs/{job_id}/publish_evidence.json
```

Search handoff writes `_active_job.json` with:

- `schema_version`, `job_type = xhs_search`, `job_id`, `account_id`, `provider_type`
- `keyword`, `limit`, `capture_screenshot`
- `evidence_output_dir`, `expected_evidence_file`
- `safe_mode = true` and instructions that forbid bypassing login or verification

Publish handoff writes `_active_publish_job.json` with:

- `schema_version`, `job_type = xhs_publish`, `job_id`, `account_id`, `provider_type`
- `title`, `body`, `tags`, `tags_json`
- `image_paths`, `image_paths_json`, `publish_mode = manual_review`
- `evidence_output_dir`, `expected_evidence_file`
- instructions that forbid bypassing login or verification and forbid final publish without manual review

APIs:

```http
POST /api/workflows/xhs/yingdao/local-handoff/search
POST /api/workflows/xhs/yingdao/local-handoff/publish
GET  /api/workflows/xhs/yingdao/local-handoff/search/{job_id}
GET  /api/workflows/xhs/yingdao/local-handoff/publish/{job_id}
GET  /api/workflows/xhs/yingdao/local-handoff/active
```

PowerShell helpers:

```powershell
.\scripts\xhs_yingdao_prepare_search_handoff.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "search-local-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
.\scripts\xhs_yingdao_check_active_job.ps1 -BaseUrl "http://127.0.0.1:8000"
.\scripts\xhs_yingdao_mock_evidence.ps1 -JobType "search" -JobId "search-local-001" -Status "success"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/workflows/xhs/yingdao/local-handoff/search/search-local-001" -Method Get

.\scripts\xhs_yingdao_prepare_publish_handoff.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "publish-local-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-local-001\01.png"
.\scripts\xhs_yingdao_mock_evidence.ps1 -JobType "publish" -JobId "publish-local-001" -Status "waiting_manual_review"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/workflows/xhs/yingdao/local-handoff/publish/publish-local-001" -Method Get
```

Common local handoff errors:

- `XHS_YINGDAO_ACTIVE_JOB_WRITE_FAILED`: local active job or manifest could not be written.
- `XHS_YINGDAO_ACTIVE_JOB_INVALID`: active job JSON is malformed.
- `XHS_YINGDAO_EVIDENCE_NOT_FOUND`: Yingdao has not written evidence yet; this maps to `waiting_rpa_result`.
- `XHS_YINGDAO_EVIDENCE_INVALID`: evidence JSON is malformed or missing required fields.
- `XHS_YINGDAO_REAL_API_DISABLED`: real Yingdao API is intentionally disabled in this task.

Readiness includes a `yingdao_local_handoff` dependency that checks local paths, script presence, provider registration, and safe mode. It does not generate active jobs and does not call Yingdao.

## Yingdao Desktop Manual Smoke Test

Task 31 adds a manual desktop smoke layer for Yingdao. The purpose is only to prove that the Yingdao desktop client can read browser-worker local active job JSON and write local receipt/evidence JSON.

This smoke test does not:

- Call Yingdao OpenAPI.
- Open KuaJingVS.
- Open Chrome or any browser.
- Open Xiaohongshu.
- Search.
- Publish.
- Click final publish.
- Write Feishu, PostgreSQL, or MinIO.

Prepare a search smoke:

```powershell
.\scripts\xhs_yingdao_desktop_smoke_prepare.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-smoke-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Prepare a publish smoke:

```powershell
.\scripts\xhs_yingdao_desktop_smoke_prepare.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-smoke-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-smoke-001\01.png"
```

Open the manual Yingdao desktop runbook:

```powershell
notepad .\scripts\xhs_yingdao_desktop_smoke_runbook.txt
```

The desktop flow should only:

1. Read `_active_job.json` or `_active_publish_job.json`.
2. Parse `job_id`, `job_type`, `account_id`, and `evidence_output_dir`.
3. Write `yingdao_smoke_receipt.json`.
4. Write `search_evidence.json` or `publish_evidence.json`.

Verify search smoke:

```powershell
.\scripts\xhs_yingdao_desktop_smoke_verify.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-smoke-001"
```

Verify publish smoke:

```powershell
.\scripts\xhs_yingdao_desktop_smoke_verify.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-smoke-001"
```

If the desktop flow is not ready yet, simulate the writeback locally:

```powershell
.\scripts\xhs_yingdao_desktop_smoke_mock_write.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-smoke-001" -Status "success"
.\scripts\xhs_yingdao_desktop_smoke_mock_write.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-smoke-001" -Status "waiting_manual_review"
```

Receipt and evidence safety fields must remain false:

- `rpa_runtime.opened_browser`
- `rpa_runtime.opened_xhs`
- `rpa_runtime.called_external_api`
- `smoke_test.opened_browser`
- `smoke_test.opened_xhs`
- `smoke_test.real_search_executed`
- `smoke_test.real_publish_executed`
- `smoke_test.clicked_final_publish`

Common desktop smoke errors:

- `XHS_YINGDAO_SMOKE_RECEIPT_NOT_FOUND`: desktop RPA has not written receipt yet.
- `XHS_YINGDAO_SMOKE_EVIDENCE_NOT_FOUND`: desktop RPA has not written mock evidence yet.
- `XHS_YINGDAO_SMOKE_RECEIPT_INVALID`: receipt JSON is malformed or unsafe.
- `XHS_YINGDAO_SMOKE_EVIDENCE_INVALID`: evidence JSON is malformed or indicates real action.
- `XHS_YINGDAO_SMOKE_BROWSER_OPEN_FORBIDDEN`: receipt/evidence says a browser was opened.
- `XHS_YINGDAO_SMOKE_XHS_OPEN_FORBIDDEN`: receipt/evidence says Xiaohongshu was opened.

Readiness includes a `yingdao_desktop_smoke` dependency that checks scripts, mock-write availability, local queue writability, safe mode, and that real Yingdao API remains disabled. It does not prepare smoke jobs, call Yingdao, access network, or open browsers.

## Yingdao Browserless Form-fill Simulator

Task 32 adds a local JSON-only form-fill simulator for Yingdao field mapping. It does not call Yingdao OpenAPI, open a browser, open local HTML, open Xiaohongshu, search, publish, or click real buttons.

The simulator package is written under:

```text
.local_rpa_queue/yingdao/simulator/{search|publish}/{job_id}/
  simulator_input.json
  form_spec.json
  expected_actions.json
  form_fill_trace.json
  simulator_result.json
  simulator_summary.json
```

File roles:

- `simulator_input.json`: job payload and local package paths.
- `form_spec.json`: fake form fields such as `keyword_input`, `title_input`, and `body_textarea`.
- `expected_actions.json`: ordered browserless fill/set actions.
- `form_fill_trace.json`: Yingdao or mock-write action trace.
- `simulator_result.json`: validation result from the fake form-fill run.

Prepare search simulator:

```powershell
.\scripts\xhs_yingdao_form_sim_prepare.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-sim-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Prepare publish simulator:

```powershell
.\scripts\xhs_yingdao_form_sim_prepare.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-sim-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-sim-001\01.png" -PublishMode "manual_review"
```

Open the runbook:

```powershell
notepad .\scripts\xhs_yingdao_form_sim_runbook.txt
```

The Yingdao desktop flow should only read `simulator_input.json`, `form_spec.json`, and `expected_actions.json`, then write `form_fill_trace.json` and `simulator_result.json`. It must not open browser, local HTML, Xiaohongshu, or click publish.

Verify:

```powershell
.\scripts\xhs_yingdao_form_sim_verify.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-sim-001"
.\scripts\xhs_yingdao_form_sim_verify.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-sim-001"
```

Mock-write for local validation:

```powershell
.\scripts\xhs_yingdao_form_sim_mock_write.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-sim-001" -Status "success"
.\scripts\xhs_yingdao_form_sim_mock_write.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-sim-001" -Status "success"
```

Common simulator errors:

- `XHS_YINGDAO_FORM_SIMULATOR_TRACE_NOT_FOUND`: `form_fill_trace.json` is not written yet.
- `XHS_YINGDAO_FORM_SIMULATOR_RESULT_NOT_FOUND`: `simulator_result.json` is not written yet.
- `XHS_YINGDAO_FORM_SIMULATOR_TRACE_INVALID`: trace JSON is malformed.
- `XHS_YINGDAO_FORM_SIMULATOR_RESULT_INVALID`: result JSON is malformed.
- `XHS_YINGDAO_FORM_SIMULATOR_FORBIDDEN_ACTION`: trace/result says browser, XHS, external API, or publish click happened.
- `XHS_YINGDAO_FORM_SIMULATOR_REQUIRED_FIELD_MISSING`: required fake form fields were not filled.
- `XHS_YINGDAO_FORM_SIMULATOR_UNEXPECTED_ACTION`: trace contains actions outside `expected_actions.json`.

Readiness includes a `yingdao_form_fill_simulator` dependency that checks scripts, local queue writability, mock-write availability, safe mode, and disabled real Yingdao API. It does not prepare packages, call Yingdao, access network, open browser, or open local HTML.

## Yingdao Local Static HTML Sandbox Simulator

Task 33 adds a local static HTML sandbox for fake form mapping. It only generates local `search_sandbox.html` / `publish_sandbox.html` plus JSON contracts. It does not call Yingdao OpenAPI, open Xiaohongshu, open external webpages, search, publish, or click a real publish button.

Sandbox files are written under:

```text
.local_rpa_queue/yingdao/sandbox/{search|publish}/{job_id}/
  sandbox_manifest.json
  search_sandbox.html or publish_sandbox.html
  sandbox_expected_dom.json
  sandbox_trace.json
  sandbox_result.json
  sandbox_summary.json
```

File roles:

- `search_sandbox.html` / `publish_sandbox.html`: local fake forms with no external JS/CSS/image dependencies.
- `sandbox_manifest.json`: local paths, `file://` URI, and forbidden real-action flags.
- `sandbox_expected_dom.json`: required fake DOM elements and expected values.
- `sandbox_trace.json`: Yingdao desktop or mock-write filled-field trace.
- `sandbox_result.json`: local validation result for required elements, mismatches, and forbidden actions.

Prepare search sandbox:

```powershell
.\scripts\xhs_yingdao_html_sandbox_prepare.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-sandbox-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Prepare publish sandbox:

```powershell
.\scripts\xhs_yingdao_html_sandbox_prepare.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-sandbox-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-sandbox-001\01.png" -PublishMode "manual_review"
```

Safely open local sandbox HTML:

```powershell
.\scripts\xhs_yingdao_html_sandbox_open.ps1 -HtmlPath ".local_rpa_queue\yingdao\sandbox\search\search-sandbox-001\search_sandbox.html"
```

The open helper refuses `http://`, `https://`, `xiaohongshu.com`, and files outside `.local_rpa_queue\yingdao\sandbox`.

Open the runbook:

```powershell
notepad .\scripts\xhs_yingdao_html_sandbox_runbook.txt
```

The Yingdao desktop flow should only open the local HTML file, fill the fake local form, and write `sandbox_trace.json` plus `sandbox_result.json`. It must not open Xiaohongshu, external webpages, or click a real publish button.

Verify:

```powershell
.\scripts\xhs_yingdao_html_sandbox_verify.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-sandbox-001"
.\scripts\xhs_yingdao_html_sandbox_verify.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-sandbox-001"
```

Mock-write for local validation:

```powershell
.\scripts\xhs_yingdao_html_sandbox_mock_write.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-sandbox-001" -Status "success"
.\scripts\xhs_yingdao_html_sandbox_mock_write.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-sandbox-001" -Status "success"
```

Common HTML sandbox errors:

- `XHS_YINGDAO_HTML_SANDBOX_TRACE_NOT_FOUND`: `sandbox_trace.json` is not written yet.
- `XHS_YINGDAO_HTML_SANDBOX_RESULT_NOT_FOUND`: `sandbox_result.json` is not written yet.
- `XHS_YINGDAO_HTML_SANDBOX_TRACE_INVALID`: trace JSON is malformed or unsafe.
- `XHS_YINGDAO_HTML_SANDBOX_RESULT_INVALID`: result JSON is malformed.
- `XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_URL`: HTML or trace indicates an external/XHS URL.
- `XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_TEXT`: HTML/result contains forbidden real-action text.
- `XHS_YINGDAO_HTML_SANDBOX_FORBIDDEN_ACTION`: trace/result indicates external API, XHS, or real publish action.
- `XHS_YINGDAO_HTML_SANDBOX_REQUIRED_ELEMENT_MISSING`: required fake DOM elements were not filled.
- `XHS_YINGDAO_HTML_SANDBOX_VALUE_MISMATCH`: filled values do not match `sandbox_expected_dom.json`.

Readiness includes a `yingdao_local_html_sandbox` dependency that checks scripts, local queue writability, mock-write availability, safe mode, forbidden external URLs, forbidden XHS URLs, and disabled real Yingdao API. It does not prepare sandboxes, call Yingdao, access network, or open Xiaohongshu.

## Yingdao Local HTML Selector Mapping Report

Task 34 adds a selector mapping report for the local HTML sandbox. It only parses local `search_sandbox.html` / `publish_sandbox.html` and `sandbox_expected_dom.json`. It does not call Yingdao OpenAPI, open Xiaohongshu, open external webpages, search, publish, or scrape real Xiaohongshu selectors.

Selector mapping files are written under:

```text
.local_rpa_queue/yingdao/selector_mapping/{search|publish}/{job_id}/
  selector_mapping_input.json
  yingdao_selector_mapping.json
  yingdao_action_sequence.json
  selector_mapping_report.md
  selector_mapping_confirmation.json
  selector_mapping_summary.json
```

File roles:

- `selector_mapping_input.json`: source sandbox manifest, HTML path, expected DOM path, and safety flags.
- `yingdao_selector_mapping.json`: element-to-selector candidates such as `#title_input`, `input[name='title_input']`, and XPath candidates.
- `yingdao_action_sequence.json`: ordered local desktop actions for the fake form.
- `selector_mapping_report.md`: human-readable mapping table and Yingdao desktop action guide.
- `selector_mapping_confirmation.json`: Yingdao desktop or mock-confirm selector confirmation.

Prepare search selector mapping:

```powershell
.\scripts\xhs_yingdao_selector_mapping_prepare.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-selector-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Prepare publish selector mapping:

```powershell
.\scripts\xhs_yingdao_selector_mapping_prepare.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-selector-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-selector-001\01.png" -PublishMode "manual_review"
```

Open the mapping report safely:

```powershell
.\scripts\xhs_yingdao_selector_mapping_open_report.ps1 -ReportPath ".local_rpa_queue\yingdao\selector_mapping\search\search-selector-001\selector_mapping_report.md"
```

The report opener refuses `http://`, `https://`, `xiaohongshu.com`, and files outside `.local_rpa_queue\yingdao\selector_mapping`.

Open the selector mapping runbook:

```powershell
notepad .\scripts\xhs_yingdao_selector_mapping_runbook.txt
```

The Yingdao desktop flow should only open the local HTML sandbox, read `selector_mapping_report.md`, confirm selectors against the fake page, and write `selector_mapping_confirmation.json`. It must not open Xiaohongshu, external webpages, or click a real publish button.

Verify:

```powershell
.\scripts\xhs_yingdao_selector_mapping_verify.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-selector-001"
.\scripts\xhs_yingdao_selector_mapping_verify.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-selector-001"
```

Mock-confirm for local validation:

```powershell
.\scripts\xhs_yingdao_selector_mapping_mock_confirm.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-selector-001" -Status "success"
.\scripts\xhs_yingdao_selector_mapping_mock_confirm.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-selector-001" -Status "success"
```

Common selector mapping errors:

- `XHS_YINGDAO_SELECTOR_MAPPING_HTML_NOT_FOUND`: local sandbox HTML is missing.
- `XHS_YINGDAO_SELECTOR_MAPPING_EXPECTED_DOM_NOT_FOUND`: expected DOM JSON is missing.
- `XHS_YINGDAO_SELECTOR_MAPPING_ELEMENT_MISSING`: required local fake element is missing or not confirmed.
- `XHS_YINGDAO_SELECTOR_MAPPING_SELECTOR_EMPTY`: selector candidate or confirmed selector is empty.
- `XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_URL`: mapping/report references a forbidden URL.
- `XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_TEXT`: mapping/report contains forbidden real-action text.
- `XHS_YINGDAO_SELECTOR_MAPPING_FORBIDDEN_ACTION`: confirmation indicates external API, XHS, or real publish action.
- `XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_NOT_FOUND`: confirmation has not been written yet.
- `XHS_YINGDAO_SELECTOR_MAPPING_CONFIRMATION_INVALID`: confirmation JSON is malformed or unsafe.

Readiness includes a `yingdao_selector_mapping` dependency that checks scripts, local queue writability, mock-confirm availability, safe mode, forbidden external URLs, forbidden XHS URLs, forbidden real publish actions, and disabled real Yingdao API. It does not prepare mappings, call Yingdao, access network, or open Xiaohongshu.

## Yingdao Actual Local HTML Form-fill Smoke

Task 35 adds an actual local form-fill smoke layer for Yingdao desktop. It reuses the local HTML sandbox and selector mapping report, then prepares a runbook for filling only the local fake HTML form.

This layer does not:

- Call Yingdao OpenAPI.
- Open Xiaohongshu.
- Open external webpages.
- Search.
- Publish.
- Click a real publish button.
- Write real Feishu, PostgreSQL, or MinIO.

Actual form-fill smoke files are written under:

```text
.local_rpa_queue/yingdao/actual_form_fill/{search|publish}/{job_id}/
  actual_form_fill_input.json
  actual_form_fill_runbook.json
  actual_form_fill_trace.json
  actual_form_fill_result.json
  actual_form_fill_summary.json
```

File roles:

- `actual_form_fill_input.json`: local HTML path/URI, selector mapping path, action sequence path, and allowed target rules.
- `actual_form_fill_runbook.json`: ordered desktop actions for the local fake form.
- `actual_form_fill_trace.json`: Yingdao desktop or mock-write trace after filling the local form.
- `actual_form_fill_result.json`: validation result for required fields, value mismatches, and forbidden actions.

Prepare search actual form-fill:

```powershell
.\scripts\xhs_yingdao_actual_form_fill_prepare.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-actual-fill-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Prepare publish actual form-fill:

```powershell
.\scripts\xhs_yingdao_actual_form_fill_prepare.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-actual-fill-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-actual-fill-001\01.png" -PublishMode "manual_review"
```

Safely open the generated local HTML:

```powershell
.\scripts\xhs_yingdao_actual_form_fill_open.ps1 -HtmlPath ".local_rpa_queue\yingdao\sandbox\search\search-actual-fill-001\search_sandbox.html"
```

The opener refuses `http://`, `https://`, `xiaohongshu.com`, and files outside `.local_rpa_queue\yingdao\sandbox`.

Open the runbook:

```powershell
notepad .\scripts\xhs_yingdao_actual_form_fill_runbook.txt
```

The Yingdao desktop flow should only open the local HTML sandbox, fill the fake form according to selector mapping, click the local simulate button, and write `actual_form_fill_trace.json` plus `actual_form_fill_result.json`.

Verify:

```powershell
.\scripts\xhs_yingdao_actual_form_fill_verify.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-actual-fill-001"
.\scripts\xhs_yingdao_actual_form_fill_verify.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-actual-fill-001"
```

Mock-write for local validation:

```powershell
.\scripts\xhs_yingdao_actual_form_fill_mock_write.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-actual-fill-001" -Status "success"
.\scripts\xhs_yingdao_actual_form_fill_mock_write.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-actual-fill-001" -Status "success"
```

Common actual form-fill errors:

- `XHS_YINGDAO_ACTUAL_FORM_FILL_TRACE_NOT_FOUND`: `actual_form_fill_trace.json` is not written yet.
- `XHS_YINGDAO_ACTUAL_FORM_FILL_RESULT_NOT_FOUND`: `actual_form_fill_result.json` is not written yet.
- `XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_URL`: trace target is not a safe local file URI.
- `XHS_YINGDAO_ACTUAL_FORM_FILL_FORBIDDEN_ACTION`: trace/result indicates XHS, external API, external URL, or real publish action.
- `XHS_YINGDAO_ACTUAL_FORM_FILL_REQUIRED_FIELD_MISSING`: required fake fields were not filled.
- `XHS_YINGDAO_ACTUAL_FORM_FILL_VALUE_MISMATCH`: filled values do not match the runbook.
- `XHS_YINGDAO_ACTUAL_FORM_FILL_REAL_ACTION_FORBIDDEN`: result reports real search or publish execution.

Readiness includes a `yingdao_actual_form_fill` dependency that checks scripts, local queue writability, mock-write availability, safe mode, forbidden external URLs, forbidden XHS URLs, forbidden real publish actions, and disabled real Yingdao API. It does not prepare actual form-fill jobs, call Yingdao, access network, or open Xiaohongshu.

## XHS Account Binding Check

Task 36 adds a local account binding check between `account_id`, the KuaJingVS profile map, readonly discovery evidence, and Yingdao actual local form-fill input. It only reads local JSON files and writes local binding contracts.

This layer does not:

- Call Yingdao OpenAPI.
- Open or close a KuaJingVS shop.
- Open Xiaohongshu.
- Open external webpages.
- Search.
- Publish.
- Click a real publish button.
- Write real Feishu, PostgreSQL, or MinIO.

Account binding files are written under:

```text
.local_rpa_queue/yingdao/account_binding/{search|publish}/{job_id}/
  account_binding_input.json
  account_binding_context.json
  account_binding_confirmation.json
  account_binding_summary.json
```

File roles:

- `account_binding_input.json`: binding job metadata, profile map path, KuaJingVS discovery evidence path, actual form-fill input path, and forbidden real-action flags.
- `account_binding_context.json`: resolved account profile, matched readonly discovery shop, warnings, errors, and safe-mode real-action flags.
- `actual_form_fill_input.json.account_binding`: the binding context attached to the local actual form-fill package.
- `account_binding_confirmation.json`: Yingdao desktop or mock-confirm acknowledgement that the local binding was checked without opening shops or Xiaohongshu.

Prepare search account binding:

```powershell
.\scripts\xhs_account_binding_prepare.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-binding-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Prepare publish account binding:

```powershell
.\scripts\xhs_account_binding_prepare.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-binding-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-binding-001\01.png" -PublishMode "manual_review"
```

Open the account binding runbook:

```powershell
notepad .\scripts\xhs_account_binding_runbook.txt
```

The manual or Yingdao desktop flow should only read `account_binding_context.json` and `actual_form_fill_input.json`, confirm `account_id`, `shop_id`, and `shop_name`, then write `account_binding_confirmation.json`. It must not open shop, close shop, open Xiaohongshu, open external webpages, call Yingdao cloud API, or click a real publish button.

Verify:

```powershell
.\scripts\xhs_account_binding_verify.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-binding-001"
.\scripts\xhs_account_binding_verify.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-binding-001"
```

Mock-confirm for local validation:

```powershell
.\scripts\xhs_account_binding_mock_confirm.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-binding-001" -Status "success"
.\scripts\xhs_account_binding_mock_confirm.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-binding-001" -Status "success"
```

Common account binding errors:

- `XHS_ACCOUNT_BINDING_PROFILE_MAP_MISSING`: `.config/kuaijingvs_profiles.json` is missing.
- `XHS_ACCOUNT_BINDING_PROFILE_MAP_INVALID`: profile map JSON is malformed or missing required fields.
- `XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND`: `account_id` is not present in the profile map.
- `XHS_ACCOUNT_BINDING_DISCOVERY_MISSING`: readonly KuaJingVS discovery evidence is not present.
- `XHS_ACCOUNT_BINDING_SHOP_UNMATCHED`: mapped `shop_id` was not found in discovery evidence.
- `XHS_ACCOUNT_BINDING_CONFIRMATION_NOT_FOUND`: confirmation has not been written yet.
- `XHS_ACCOUNT_BINDING_CONFIRMATION_INVALID`: confirmation JSON is malformed or mismatched.
- `XHS_ACCOUNT_BINDING_FORBIDDEN_ACTION`: confirmation says shop/XHS/external/Yingdao/KuaJingVS action happened.
- `XHS_ACCOUNT_BINDING_REAL_ACTION_FORBIDDEN`: confirmation says real search or publish happened.

Readiness includes an `xhs_account_binding` dependency that checks profile map presence/validity, discovery evidence presence, local queue writability, scripts, mock-confirm availability, safe mode, forbidden open-shop actions, forbidden XHS URLs, and forbidden real publish actions. It does not prepare bindings, call KuaJingVS discovery, call Yingdao, access network, open shops, or open Xiaohongshu.

## KuaJingVS Discovery Evidence Hardening

Task 37 adds local hardening for KuaJingVS readonly discovery evidence. It only reads local `discovery.json`, writes sanitized local evidence, and prepares that evidence for strict account binding.

This layer does not:

- Open shop.
- Close shop.
- Open Xiaohongshu.
- Open external webpages.
- Call Yingdao OpenAPI.
- Search.
- Publish.

Hardened discovery files are written under:

```text
.local_evidence/kuaijingvs_discovery/
  discovery.json
  hardened_discovery.json
  hardened_discovery_summary.json
  hardened_discovery_audit.json
```

File roles:

- `hardened_discovery.json`: safe readonly shop projection with `shop_id`, `shop_name`, `provider_type`, `raw_keys`, safety flags, and `evidence_hash`.
- `hardened_discovery_summary.json`: compact readiness summary for strict binding.
- `hardened_discovery_audit.json`: local audit snapshot for the hardening run.

Sensitive keys are removed before hardened evidence is written. The filter covers at least `token`, `access_token`, `refresh_token`, `cookie`, `set-cookie`, `secret`, `password`, `passwd`, `authorization`, `auth`, `api_key`, `app_secret`, `session`, `credential`, and `private_key`. Sensitive value scanning rejects patterns such as `Bearer`, `sessionid=`, `access_token=`, `refresh_token=`, `password=`, `secret=`, and `Authorization`.

`evidence_hash` is a SHA-256 hash over the hardened evidence payload. It helps detect accidental local changes before strict account binding.

Run hardening:

```powershell
.\scripts\xhs_kjvs_discovery_harden.ps1 -BaseUrl "http://127.0.0.1:8000" -SourceEvidencePath ".local_evidence\kuaijingvs_discovery\discovery.json"
```

Common hardening errors:

- `XHS_KJVS_DISCOVERY_SOURCE_NOT_FOUND`: source `discovery.json` does not exist.
- `XHS_KJVS_DISCOVERY_HARDENED_INVALID`: hardened evidence is malformed or failed validation.
- `XHS_KJVS_DISCOVERY_SENSITIVE_FIELD_DETECTED`: a sensitive key remained in hardened evidence.
- `XHS_KJVS_DISCOVERY_SENSITIVE_VALUE_DETECTED`: source evidence contains a sensitive-looking value.
- `XHS_KJVS_DISCOVERY_HASH_FAILED`: hash computation failed.

Readiness includes a `kuaijingvs_discovery_hardening` dependency. It does not harden automatically, call KuaJingVS live APIs, open shops, or open Xiaohongshu.

## XHS Account Binding Strict Mode

Task 37 also adds strict account binding checks. Strict mode depends on a valid profile map and safe `hardened_discovery.json`.

Strict mode requires:

- Profile map exists and is valid.
- `account_id` exists in the profile map.
- Hardened discovery exists and is safe.
- `shop_id` matches hardened discovery.
- `shop_name` matches hardened discovery by default.
- `provider_type` is allowed.
- Hardened evidence contains no sensitive fields or unsafe flags.

Strict binding files are written under:

```text
.local_rpa_queue/yingdao/account_binding/strict/{search|publish}/{job_id}/
  strict_binding_input.json
  strict_binding_result.json
  strict_binding_summary.json
```

Run search strict binding:

```powershell
.\scripts\xhs_account_binding_strict_check.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-strict-binding-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Run publish strict binding:

```powershell
.\scripts\xhs_account_binding_strict_check.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-strict-binding-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-strict-binding-001\01.png" -PublishMode "manual_review"
```

Open the strict runbook:

```powershell
notepad .\scripts\xhs_account_binding_strict_runbook.txt
```

Common strict binding errors:

- `XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_MISSING`: hardened discovery is missing.
- `XHS_ACCOUNT_BINDING_STRICT_DISCOVERY_UNSAFE`: hardened discovery failed safety checks.
- `XHS_ACCOUNT_BINDING_ACCOUNT_NOT_FOUND`: account is missing from profile map.
- `XHS_ACCOUNT_BINDING_STRICT_SHOP_UNMATCHED`: `shop_id` does not match hardened discovery.
- `XHS_ACCOUNT_BINDING_STRICT_SHOP_NAME_MISMATCH`: `shop_name` mismatch failed strict mode.
- `XHS_ACCOUNT_BINDING_STRICT_PROVIDER_TYPE_INVALID`: provider type is not allowed.

Readiness includes `xhs_account_binding_strict_mode`. It does not run strict checks automatically, call KuaJingVS live APIs, call Yingdao, open shops, access network, or open Xiaohongshu.

## Local n8n/OpenClaw Contract Replay

Task 38 adds local contract replay for n8n and OpenClaw payloads. It only calls browser-worker local mock contract routes and writes local JSON files. It does not call real n8n, real OpenClaw, Yingdao OpenAPI, KuaJingVS open shop, Xiaohongshu, Feishu, PostgreSQL, or MinIO.

Replay files are written under:

```text
.local_rpa_queue/replay/
  n8n/{search|publish}/{job_id}/
    replay_payload.json
    replay_result.json
    replay_summary.json
  openclaw/job_status/{job_id}/
    replay_payload.json
    replay_result.json
    replay_summary.json
```

File roles:

- `replay_payload.json`: local n8n/OpenClaw mock contract payload with strict account binding context and hardened discovery reference.
- `replay_result.json`: local route replay result, local route path, strict binding status, sensitive scan result, and real-action flags.
- `replay_summary.json`: compact summary for contract review and future real workflow design.

The replay payload carries `strict_account_binding` from `strict_binding_result.json` and `hardened_discovery` from `hardened_discovery.json`. Payloads are sanitized and rejected if they contain sensitive keys or values such as token, cookie, secret, password, auth, authorization, header, Bearer, or sessionid.

Run n8n search replay:

```powershell
.\scripts\xhs_contract_replay_n8n_search.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "search-replay-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Run n8n publish replay:

```powershell
.\scripts\xhs_contract_replay_n8n_publish.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "publish-replay-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-replay-001\01.png" -PublishMode "manual_review"
```

Run OpenClaw job-status replay:

```powershell
.\scripts\xhs_contract_replay_openclaw_status.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "publish-replay-001" -JobType "xhs_publish" -AccountId "xhs_dev_01"
```

Run replay all:

```powershell
.\scripts\xhs_contract_replay_all.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-replay-all-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Common replay errors:

- `XHS_CONTRACT_REPLAY_STRICT_BINDING_MISSING`: strict binding result is missing.
- `XHS_CONTRACT_REPLAY_STRICT_BINDING_FAILED`: strict binding is not `strict_matched`.
- `XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_MISSING`: hardened discovery is missing.
- `XHS_CONTRACT_REPLAY_HARDENED_DISCOVERY_UNSAFE`: hardened discovery failed safety checks.
- `XHS_CONTRACT_REPLAY_SENSITIVE_PAYLOAD_DETECTED`: replay payload contains sensitive fields or values.
- `XHS_CONTRACT_REPLAY_EXTERNAL_CALL_FORBIDDEN`: an external URL replay was attempted.
- `XHS_CONTRACT_REPLAY_LOCAL_ROUTE_FAILED`: local mock route replay failed.

Readiness includes `local_contract_replay`. It does not replay automatically, call real n8n/OpenClaw, open shops, access network, or open Xiaohongshu.

## Local Feishu/PostgreSQL/MinIO Mock Persistence Replay

Task 39 adds local-only persistence replay after Task 38 contract replay. It reads `replay_result.json` / `replay_summary.json`, strict account binding, and hardened discovery references, then writes local mock payloads under `.local_rpa_queue/persistence`.

It does not write real Feishu, connect real PostgreSQL, upload real MinIO, call real n8n/OpenClaw, call Yingdao OpenAPI, open shop, open Xiaohongshu, open external pages, search, or publish.

Generated files:

- `persistence_payload.json`: Feishu/PostgreSQL mock field and table mapping.
- `object_manifest.json`: MinIO mock object-key manifest.
- `persistence_result.json`: local validation result.
- `persistence_summary.json`: strict context, hardened discovery, and sensitive-scan summary.

Run all search persistence replay:

```powershell
.\scripts\xhs_persistence_replay_all.ps1 -JobType "search" -BaseUrl "http://127.0.0.1:8000" -JobId "search-persist-001" -AccountId "xhs_dev_01"
```

Run all publish persistence replay:

```powershell
.\scripts\xhs_persistence_replay_all.ps1 -JobType "publish" -BaseUrl "http://127.0.0.1:8000" -JobId "publish-persist-001" -AccountId "xhs_dev_01"
```

Target-specific scripts are available for Feishu, PostgreSQL, and MinIO search/publish replay. Common errors include source contract replay missing/invalid, strict binding missing/failed, hardened discovery missing/unsafe, sensitive payload detected, unsupported target, and external write forbidden.

## Local Full E2E Replay Orchestrator

Task 40 adds a local-only E2E replay orchestrator. It chains readiness, strict account binding, hardened discovery, local n8n/OpenClaw contract replay, and local Feishu/PostgreSQL/MinIO mock persistence replay into one checkpoint run.

It only writes local JSON under `.local_rpa_queue/e2e/{run_id}/`. It does not write real Feishu, connect real PostgreSQL, upload real MinIO, call real n8n/OpenClaw, call Yingdao OpenAPI, open shop, open Xiaohongshu, open external pages, search, or publish.

Generated files:

- `e2e_input.json`: local E2E input and forbidden-action boundary.
- `e2e_result.json`: step-level checkpoint result and failure details.
- `e2e_summary.json`: readiness, strict binding, hardened discovery, contract replay, and persistence replay status.
- `e2e_artifacts_manifest.json`: generated local artifact references for this run.

Run search E2E:

```powershell
.\scripts\xhs_e2e_replay_search.ps1 -BaseUrl "http://127.0.0.1:8000" -RunId "e2e-search-001" -JobId "search-e2e-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20
```

Run publish E2E:

```powershell
.\scripts\xhs_e2e_replay_publish.ps1 -BaseUrl "http://127.0.0.1:8000" -RunId "e2e-publish-001" -JobId "publish-e2e-001" -AccountId "xhs_dev_01" -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-e2e-001\01.png" -PublishMode "manual_review"
```

Run all E2E:

```powershell
.\scripts\xhs_e2e_replay_all.ps1 -BaseUrl "http://127.0.0.1:8000" -RunId "e2e-all-001" -AccountId "xhs_dev_01" -Keyword "眼影" -Limit 20 -Title "测试标题" -Body "测试正文" -Tags "眼影,美妆" -ImagePaths ".local_assets\publish-e2e-001\01.png" -PublishMode "manual_review"
```

Common errors include readiness failed, strict binding failed, hardened discovery failed, contract replay failed, persistence replay failed, sensitive payload detected, external call forbidden, result invalid, and artifact manifest invalid.

## PostgreSQL Real Persistence Adapter Phase 1

Task 41 adds controlled PostgreSQL persistence from the local Task 39 PostgreSQL replay payload. By default it is safe dry-run only:

- `XHS_POSTGRES_PERSISTENCE_ENABLED=false`
- `XHS_ALLOW_REAL_POSTGRES_WRITE=false`
- `XHS_POSTGRES_PERSISTENCE_DRY_RUN=true`

Dry-run reads `.local_rpa_queue/persistence/postgres/{search|publish}/{job_id}/persistence_payload.json`, builds an insert plan, and writes local evidence under `.local_rpa_queue/postgres_persistence/{search|publish}/{job_id}/`. It does not connect to PostgreSQL and does not write the database.

Generated files:

- `postgres_persistence_plan.json`: planned target tables, columns, and values.
- `postgres_persistence_result.json`: dry-run/write result, rows planned, rows written, and error details.
- `postgres_persistence_summary.json`: payload scan, target tables, and forbidden-action summary.

Schema file:

```text
database/xhs_persistence_schema.sql
```

The schema defines `xhs_search_evidence`, `xhs_search_records`, `xhs_publish_evidence`, `xhs_publish_jobs`, `xhs_task_log`, and `xhs_workflow_log` with indexes for `job_id`, `account_id`, `keyword` where applicable, and `created_at`.

Check schema and readiness:

```powershell
.\scripts\xhs_postgres_schema_check.ps1 -BaseUrl "http://127.0.0.1:8000"
```

Apply schema is dry-run unless `-ConfirmApply` is provided:

```powershell
.\scripts\xhs_postgres_apply_schema.ps1 -SchemaPath "database\xhs_persistence_schema.sql"
```

Dry-run persist search replay:

```powershell
.\scripts\xhs_postgres_persist_search_replay.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "search-pg-001" -AccountId "xhs_dev_01" -DryRun
```

Dry-run persist publish replay:

```powershell
.\scripts\xhs_postgres_persist_publish_replay.ps1 -BaseUrl "http://127.0.0.1:8000" -JobId "publish-pg-001" -AccountId "xhs_dev_01" -DryRun
```

Real PostgreSQL writes require all of these at the same time: `dry_run=false`, `XHS_POSTGRES_PERSISTENCE_ENABLED=true`, and `XHS_ALLOW_REAL_POSTGRES_WRITE=true`. The service rejects payloads containing token, cookie, secret, password, auth, authorization, header, Bearer, or session-like values.

Task 41 does not write Feishu, upload MinIO, call real n8n/OpenClaw, call Yingdao OpenAPI, open shop, open Xiaohongshu, open external pages, search, or publish.
