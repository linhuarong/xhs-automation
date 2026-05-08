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
$env:RPA_LOCAL_EVIDENCE_ROOT = ".local_evidence"
```

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
