# XHS Agent Rules

This document defines how Codex / coding agents should work in this repository.

## Mandatory reading order

For any task touching Xiaohongshu automation, read these first:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/09_小红书自动化工作流_RPA重构版_V2.md`
4. The most relevant domain doc under `docs/`
5. The exact files named in the task

Do not scan the whole repository unless the task explicitly requires it.

## Current architecture boundary

The main path is:

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

`selenium_chrome` is debug-only. Do not promote direct Selenium page execution to the main production path.

## Task discipline

Every coding task must have:

- Task id or short title
- Goal
- Allowed files
- Forbidden files / forbidden scope
- Acceptance criteria
- Minimal test command
- Expected output format

If these are missing, produce a short task-intake note before editing code.

## Scope control

Prefer one narrow vertical slice per task. A good task changes a small set of files and proves one behavior.

Avoid:

- broad refactors
- unrelated cleanup
- hidden behavior changes
- full workflow rewrites
- long generated explanations in code comments

## Testing rules

Prefer the smallest deterministic test first.

Allowed by default:

- Unit tests with mocks
- Local fixture replay
- Schema validation tests
- Evidence JSON parsing tests

Not allowed by default:

- Live Xiaohongshu execution
- Real Yingdao OpenAPI calls
- Real KuaJingVS OpenAPI calls
- Real Feishu / MinIO / PostgreSQL writes
- Full E2E replay unless explicitly requested

## Evidence rules

Any workflow result should be traceable through evidence.

For search workflow, preserve:

- `search_evidence.json`
- screenshot path or future MinIO object key
- `normalized_records`
- status and error code

For publish workflow, preserve:

- `publish_evidence.json`
- screenshots for important stages
- input title/body/images summary
- status and error code

## Manual checkpoint rule

When a flow reaches a checkpoint that requires a person, return:

```text
waiting_human_verification
```

Also preserve screenshot and error context.

## Output rule for Codex

At the end of a task, output only:

1. Modified files
2. Test command
3. Test result
4. Risks / unfinished items
5. Whether human review is needed

Do not paste full logs unless the task asks for them.
