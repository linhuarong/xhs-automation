---
name: xhs-handoff
description: Use when closing a development window, preparing a new ChatGPT/Codex window, summarizing current XHS automation progress, or updating handoff docs after a task.
---

# XHS Handoff Skill

Use this skill to produce compact, high-signal project handoffs.

Do not paste entire conversations. Reference files, commits, PRs, and evidence paths instead.

## Mandatory context

Read first:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/agents/xhs-handoff-template.md`
4. Current task output
5. Git diff / PR / commit metadata if available

## Handoff principles

A good handoff should answer:

- What task was being done?
- What files changed?
- What tests passed or failed?
- What evidence was created?
- What decision was made?
- What risk remains?
- What exact task should the next window do?

Avoid:

- full raw logs
- full chat transcripts
- repeated architecture explanations already present in docs
- copying large JSON unless it is the artifact being debugged

## Required sections

Use this structure:

```markdown
# XHS Handoff｜<task or date>

## 1. Current status

- Task:
- Branch:
- Latest commit:
- PR:
- Status:

## 2. Changes made

- Modified files:
- Behavior added or changed:

## 3. Tests

- Command:
- Result:

## 4. Evidence / artifacts

- Evidence:
- Screenshot:
- JSON:
- Log:

## 5. Decisions

- Decision:
- Reason:
- Source:

## 6. Risks / unfinished items

- Risk:
- Next action:

## 7. Next task recommendation

Task:
Goal:
Allowed files:
Test command:
```

## Repository hygiene checklist

Mention if any of these need cleanup:

- `.local_evidence/`
- `.local_screenshots/`
- `.local_profiles/`
- temporary `*_check.json`
- credentials or local config
- uncommitted branch changes

## Next-window starter prompt

End with a copy-ready starter prompt:

```text
请读取 AGENTS.md、CONTEXT.md、docs/agents/xhs-agent-rules.md，以及本次 handoff。当前分支是 <branch>，上一任务状态是 <status>。请先确认 git/PR 状态，再进入 <next task>。
```
