---
name: workhunt-maintain-sources
description: Maintain the public employer-board registry, private overrides, provenance and observed health for a requested source import or registry check. Does not start a job search or connect accounts.
---

# Maintain employer sources

Read the [shared context](references/workspace/docs/skills/WORKHUNT_CONTEXT.md.md) and [source maintenance guide](references/workspace/sources/EMPLOYER_SOURCES.md.md). Resolve the shared release root independently of the private `.workhunt` directory. The pinned public snapshot contains board identities, including public Comeet identifiers; an import is not a successful live probe.

1. Establish the requested import/check scope. Use the pinned snapshot for offline checks. A source refresh or live board probe needs explicit current authorization; this skill does not supply it.
2. Read the shared registry, private registry if present, private override file and observed health. Keep stable provider/region/tenant identities. Local disabled overrides win over directory discovery and extra-board settings.
3. Run `tools/maintain_workhunt_sources.py --workspace PATH --snapshot SNAPSHOT --dry-run` from the shared release. Inspect provenance, counts, additions, missing-upstream markers and conflicts. `--check` exits nonzero when the candidate differs.
4. Apply only the requested local registry change with `--apply`. The write target is private `.workhunt/sources/`; do not populate the distributed shared seed with personal choices or runtime observations. Repeat the check to establish idempotence.
5. Preserve previous successful observations when a new check fails. Missing upstream is not a closed employer; imported is not verified; an accessible board is not an available application route. Record only actual observations with timestamps.
6. Report actual changed counts and limitations. Retain attribution and pinned provenance. Never upload CVs, connect accounts, submit applications, replace private overrides, or infer authorization from saved notes.

## Workspace resolution

Run this skill's `scripts/resolve_workspace.py [--workspace PATH]` when the workspace is uncertain. Precedence is explicit path, current checkout, then private `workspace.local.json` fallback; `workspace.json` is an unbound portable descriptor. Shared references under `references/workspace/` point to exact files in that resolved workspace; private records and CVs are never bundled. Keep automatic skill selection enabled.
