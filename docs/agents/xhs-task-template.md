# XHS Codex Task Template

Copy this template when creating a new Codex task.

```text
Task: <Task number and short title>

Read first:
- AGENTS.md
- CONTEXT.md
- docs/09_小红书自动化工作流_RPA重构版_V2.md
- <domain-specific docs>

Goal:
- <one narrow behavior to implement or verify>

Allowed files:
- <exact file path>
- <exact file path>

Do not modify:
- <forbidden file or directory>
- <forbidden behavior>

Constraints:
- Keep provider boundary intact.
- Keep selenium_chrome debug-only unless this is a debug task.
- Do not call real external services unless explicitly required.
- Use fixture / mock / local replay where possible.

Acceptance criteria:
1. <observable result>
2. <observable result>
3. <test expectation>

Test command:
```powershell
<minimal pytest or script command>
```

Required final output:
1. Modified files
2. Test command
3. Test result
4. Risks / unfinished items
5. Whether human review is needed
```

## Good task examples

```text
Task 42A: Add evidence parser for Yingdao search output

Allowed files:
- services/browser-worker/app/services/yingdao_evidence_parser.py
- services/browser-worker/tests/test_yingdao_evidence_parser.py

Test command:
pytest services/browser-worker/tests/test_yingdao_evidence_parser.py -q
```

```text
Task 42B: Add provider router unit tests for kuaijingvs_yingdao_rpa

Allowed files:
- services/browser-worker/app/providers/__init__.py
- services/browser-worker/tests/test_provider_router.py

Test command:
pytest services/browser-worker/tests/test_provider_router.py -q
```

## Bad task examples

Avoid tasks like:

```text
Continue the whole project.
Fix all RPA issues.
Implement full Xiaohongshu automation.
Read the whole repo and decide what to do.
Run all E2E tests and repair everything.
```
