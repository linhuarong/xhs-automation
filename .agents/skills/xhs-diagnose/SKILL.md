---
name: xhs-diagnose
description: Use when an XHS automation test, evidence flow, provider integration, RPA dispatch, or local replay fails and the next step should be a structured diagnosis rather than a broad rewrite.
---

# XHS Diagnose Skill

Use this skill for failures in:

- browser-worker API
- Provider Router
- KuaJingVSOpenAPI adapter
- YingdaoService adapter
- evidence JSON parsing
- normalized_records generation
- local replay scripts
- pytest / fixture tests
- n8n callback payload simulation

## Goal

Build a small, deterministic feedback loop before changing code.

Do not rewrite large areas while guessing.

## Mandatory context

Read first:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/agents/xhs-agent-rules.md`
4. The failing file / test / script
5. The smallest related implementation file

## Diagnosis loop

Follow this order:

1. State the observed failure.
2. Identify the smallest reproducible command or fixture.
3. Classify the failure type.
4. Propose 3–5 falsifiable hypotheses.
5. Test one hypothesis at a time.
6. Make the smallest fix.
7. Add or update a regression test.
8. Remove temporary debug output.
9. Report the result in compact form.

## Failure classes

Use these labels:

- `schema_contract_failure`
- `provider_routing_failure`
- `evidence_parse_failure`
- `normalized_record_failure`
- `mock_boundary_failure`
- `external_call_leak`
- `local_path_failure`
- `encoding_failure`
- `state_transition_failure`
- `test_fixture_failure`

## External boundary checks

Before fixing, check whether the failure accidentally touches external services.

Unit tests must not call:

- real Xiaohongshu
- real Yingdao OpenAPI
- real KuaJingVS OpenAPI
- real Feishu
- real MinIO
- real PostgreSQL

If a unit test needs one of these, replace it with a mock, fixture, or local replay.

## Evidence checks

For evidence-related bugs, verify:

- JSON is UTF-8
- required fields exist
- `status` is valid
- `job_id` is preserved
- `provider_type` is preserved
- paths are stable for local or MinIO mode
- `items` and `normalized_records` counts match expected behavior
- manual-checkpoint status preserves error context

## Output format

Return exactly:

```text
Diagnosis:
- Failure:
- Repro command:
- Failure class:

Hypotheses:
1.
2.
3.

Chosen fix:
-

Modified files:
-

Test command:
-

Test result:
-

Remaining risk:
-
```

Do not paste full logs unless the key failure line is required.
