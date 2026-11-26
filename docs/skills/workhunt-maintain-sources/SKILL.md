---
name: workhunt-maintain-sources
description: Maintain the public employer-board registry, private overrides, provenance and observed health for a requested source import or registry check. Does not start a job search or connect accounts.
---

# Maintain employer sources

Read the [shared context](../WORKHUNT_CONTEXT.md) and [source maintenance guide](../../../sources/EMPLOYER_SOURCES.md). Resolve the shared release root independently of the private `.workhunt` directory. The pinned public snapshot contains board identities, including public Comeet identifiers; an import is not a successful live probe.

1. Establish the requested import/check scope. Use the pinned snapshot for offline checks. A source refresh or live board probe needs explicit current authorization; this skill does not supply it.
2. Read the shared registry, private registry if present, private override file and observed health. Keep stable provider/region/tenant identities. Local disabled overrides win over directory discovery and extra-board settings.
3. Run `tools/maintain_workhunt_sources.py --workspace PATH --snapshot SNAPSHOT --dry-run` from the shared release. Inspect provenance, counts, additions, missing-upstream markers and conflicts. `--check` exits nonzero when the candidate differs.
4. Apply only the requested local registry change with `--apply`. The write target is private `.workhunt/sources/`; do not populate the distributed shared seed with personal choices or runtime observations. Repeat the check to establish idempotence.
5. Preserve previous successful observations when a new check fails. Missing upstream is not a closed employer; imported is not verified; an accessible board is not an available application route. Record only actual observations with timestamps.
6. Report actual changed counts and limitations. Retain attribution and pinned provenance. Never upload CVs, connect accounts, submit applications, replace private overrides, or infer authorization from saved notes.

Read [manual discovery](references/MANUAL_DISCOVERY.md) and the shared 28-source catalog: the original 23 IDs and evidence remain, with Arc, Hacker News, Scalable Path, X-Team and Gun.io added and Guru enriched. Select routes using current candidate settings and the active request. Offline `discovery_routes.py` resolves aliases for source planning only; it neither fetches nor updates health. Generic intake does not count as an opportunity; exact agency vacancy screening remains eligible for the normal checks. A reviewed or attached request template does not invoke a search.

Prefer documented working URL/method pairs before known failing defaults; preserve functional queries and redirects, bounded readiness and per-employer evidence. Continue actual partial-list pagination and stop completed scopes or exhausted pairs. Read the manual guide for historical recovery limits. Exact identified project invitations may undergo normal qualification; generic intake cannot. Keep HN item identity separate from normalized, explicitly evidenced employer requisition aliases.

Bind each observation and attempt to one consistent source/employer identity and exact route or paired navigation before coverage/fallback decisions. Other targets stay `not_attempted`; shared hosts and conflicting identities do not establish ownership. Keep one explicit bounded observation per target and retain private diagnostics without merging categories into whole-board coverage. Read the manual guide's binding contract.
