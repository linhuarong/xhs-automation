---
name: xhs-task-slice
description: Use when converting a broad Xiaohongshu automation request into a small Codex-ready development task with strict scope, allowed files, forbidden scope, and minimal tests.
---

# XHS Task Slice Skill

Use this skill before coding when the request is broad, ambiguous, or likely to touch multiple components.

## Purpose

Convert a large request into one narrow vertical slice that Codex can implement safely and cheaply.

The output should be a task prompt, not code.

## Mandatory context

Read first:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/agents/xhs-agent-rules.md`
4. `docs/09_小红书自动化工作流_RPA重构版_V2.md`
5. The relevant domain doc under `docs/`

## Slice rules

A valid slice must have:

- one goal
- one subsystem
- explicit allowed files
- explicit forbidden files or behavior
- one minimal test command
- clear acceptance criteria
- short final-output format

Prefer 3–6 editable files. Avoid broad edits.

## Architecture guardrails

Keep the current architecture boundary:

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

Rules:

- `kuaijingvs_yingdao_rpa` is the main production-oriented path.
- `yingdao_rpa` is for local RPA smoke / integration.
- `selenium_chrome` is debug-only.
- Unit tests must mock external services.
- Evidence JSON is the contract between RPA execution and browser-worker.

## Output format

Return exactly this structure:

```text
Task: <task id and title>

Read first:
- AGENTS.md
- CONTEXT.md
- docs/agents/xhs-agent-rules.md
- docs/09_小红书自动化工作流_RPA重构版_V2.md
- <domain doc>

Goal:
- <single behavior>

Allowed files:
- <path>
- <path>

Do not modify:
- <path or scope>

Constraints:
- <constraint>
- <constraint>

Acceptance criteria:
1. <criterion>
2. <criterion>
3. <criterion>

Test command:
<minimal test command>

Required final output:
1. Modified files
2. Test command
3. Test result
4. Risks / unfinished items
5. Whether human review is needed
```

## When the request is too large

Split it into sub-tasks:

```text
Task 42A: schema only
Task 42B: service only
Task 42C: provider wiring only
Task 42D: local replay only
Task 42E: docs and handoff only
```

Recommend the first sub-task only. Do not attempt to implement all sub-tasks at once.
