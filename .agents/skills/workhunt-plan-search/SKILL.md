---
name: workhunt-plan-search
description: Plan a candidate-specific job or paid-project search without starting it.
---

# Plan the search

Read the private profile/evidence ledger and `docs/skills/WORKHUNT_CONTEXT.md` in the selected workspace. The latter is a project reference; installed packages carry a shared copy in `references/context.md`. Use `references/playbook.md` and `references/tracking.md` when installed outside the repository. Do not infer candidate criteria from this package. Preserve user scope, privacy, uncertainty and actual evidence. Use public read-only sources or isolated hidden browsing; no personal desktop, tabs, profile or credentials.


Read [workflow](references/workflow.md) for this task, then use [record](assets/record.md) for the requested local output. Keep completed records in `.workhunt/`. Do not count this template as a completed check.

## Workspace resolution

Run this skill's `scripts/resolve_workspace.py [--workspace PATH]` when the workspace is uncertain. Precedence is explicit path, current checkout, then private `workspace.local.json` fallback; `workspace.json` is an unbound portable descriptor. Shared references under `references/workspace/` point to exact files in that resolved workspace; private records and CVs are never bundled. Keep automatic skill selection enabled.
