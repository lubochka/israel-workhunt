# Reusable Workhunt manual-search prompt

<!-- Workhunt public prompt: unfilled candidate-configured workflow; completed requests stay private. -->

Execute this workflow only when the user explicitly invokes it as a new manual search. Attaching, copying, publishing, reviewing or repairing this document is not invocation and authorizes no search, new run or canonical-record changes. The instructions below apply only after that explicit invocation.

This is the complete public workflow. The [private search-request template](templates/search-request.template.md) supplies invocation parameters; it does not replace these phases. Resolve the current request and explicit private configuration into one complete run brief. Unknown facts remain unknown. This document supplies no candidate identity, country, technology stack, duration, requested minimum, result cap or permission to act externally. Store completed requests and all evidence under the selected workspace's ignored `.workhunt/` directory.

After invocation, carry out the authorized research and deliver the evidence-supported set of distinct, newly recommendable employment, contract and paid-client opportunities in the requested lanes. A plan alone is not delivery. Use only currently authorized public search/page tools and an isolated hidden/headless browser. This manual workflow does not authorize collectors or platform API integrations, tool installation, product/skill changes, applications, bids, contact, CV uploads, account connections, access purchases, mailboxes, subscriptions or schedules. Do not interrupt the user with questions; continue independent work and report material blockers at the end. A later direct bounded instruction is a separate authorization, not a permission inferred from this prompt.

## 1. Read the project and preserve current criteria

Resolve the actual shared Workhunt checkout and the selected private working directory using the supported workspace resolver. Read [AGENTS.md](AGENTS.md), [shared context](docs/skills/WORKHUNT_CONTEXT.md), [tracking](docs/skills/JOB_TRACKING.md), `.workhunt/profile.json` and `.workhunt/profile-evidence.json`. Follow the private profile's `cv_manifest` pointer to the current language/role versions. Read the actual selected CV content and relevant direct user confirmations; a filename or matching hash does not prove that a CV was read. Missing or unconfigured settings block dependent research; do not invent defaults or modify the profile during a search.

Read `.workhunt/data/applied_jobs.json` and `.workhunt/data/jobs.json` before discovery. Inspect recent `search_runs` and relevant private research records for attempted sources, unresolved promising leads and recurring blockers. Historical records supply leads and history, not current verification.

Use the focused skills `workhunt-plan-search`, `workhunt-find-job-leads`, `workhunt-find-freelance-projects`, `workhunt-assess-job-fit`, `workhunt-check-job-freshness`, `workhunt-verify-application-route`, `workhunt-reconcile-job-history` and `workhunt-report-new-matches`. Read their canonical guidance and necessary references, the [placement map](docs/skills/SOURCE_AND_PLACEMENT_MAP.md) and relevant [playbook](JOB_SEARCH_PLAYBOOK.md) sections. The current direct request and current project contracts take precedence over stale packaged wording. Do not install or rewrite skills during this research.

## 2. Create a new manual run with the resolved fixed windows

Resolve the invocation's duration or source-specific durations, time zone, requested minimum, optional cap, tracks, capabilities, source selection and allowed methods from the current explicit request and confirmed private settings. A one-run override changes this run only. Do not reinterpret an attached example as an override or rewrite persistent preferences, collector/notification settings or historical snapshots.

Capture one anchor **T** when the authorized search begins. For each applicable source group, calculate **S(group) = T minus its resolved elapsed-hour duration through UTC**; express the bounds in the configured IANA time zone as aware ISO timestamps. Keep each **[S(group), T]** fixed for the entire run, including clock changes. Calendar dates and fixed UTC offsets do not substitute for elapsed time.

Create a unique search-run ID and save a modern `search_brief` containing:

- `run_type: manual` and `execution_context: manual`.
- Actual `window_start`, `window_end` and `timezone`, with the resolved base window and anchor.
- The actual `requested_minimum` and `result_cap`; null means no cap only when that is the resolved instruction, not an invented target.
- Explicit `source_windows.other`, `source_windows.employer_registry` and `source_windows.techmap` with their resolved hours and bounds. If an explicit all-source override applies, record that same interval consistently in every group; otherwise preserve the resolved group distinctions.
- Requested tracks, supported capability criteria and source selection.
- Actual authorized methods/actions and attributed current policy provenance, without copying permission from historical notes.

Use computed timestamps, never literal placeholders. Do not carry a contradictory old fallback into a new snapshot or reuse an old run as this new invocation. Retain truthful source membership even when all groups share one window. Exact opportunity ID and listing URL must pair on one identity or evidenced alias for any source-specific exception; unsupported membership uses this run's recorded `other` window.

Read [runtime commands](docs/WORKHUNT_RUNTIME.md) and the [runtime schema](skills/workhunt-search/references/runtime.md). A scalar freshness preference does not replace explicit saved bounds. Collector, notification, assessment and fixture behavior remains 24 elapsed hours; do not invent widening flags, relabel a collector as manual or repair it during this search. Public research must cover the resolved manual interval. Scanner snapshots and zero-qualified counts are discovery evidence, not final results. If an authorized local renderer or packet helper is used, explicitly select this new run through its real selector. Keep saved run-ID/copied-brief context, provenance and original windows intact.

## 3. Maximize suitable opportunities without weakening qualification

Pursue the resolved requested minimum across the selected engagement types. A minimum is a target, not a guarantee or an automatic stopping rule. Respect an explicit cap; otherwise continue accessible planned coverage without inventing one. When jobs and projects are both requested, research both throughout the run; extra jobs do not substitute for an unsearched project lane, and no quota per category is implied.

Use only the profile/request's chosen role families, seniority, capabilities, accepted alternatives and engagement types. Search development, hands-on leadership, analysis or other families separately when selected. Concrete paid work may involve implementation, modernization, integration, performance, review or temporary leadership when supported and requested. Determine type from the actual brief, not the platform name. Label a genuinely accepted alternative; adjacent stacks, delivery-only work or other tracks require explicit inclusion. Broad discovery patterns do not change qualification criteria.

After reading the complete description, apply the exact fit rule:

- Extract distinct mandatory skill/experience criteria before scoring. Count each once. A skill plus its required duration is one criterion; explicitly accepted alternatives form one criterion.
- Exclude preferences, repeated wording, incidental mentions and general duties from the denominator. Do not omit difficult requirements or split easy ones to inflate the score.
- Supported requirement earns 1; unmet or unverified requirement earns 0 and stays in the denominator. Record evidence or a gap for every criterion.
- Accept exactly 75% with `4*M >= 3*N` before rounding. Show M/N, percentage and gaps. An ordinary gap is not an independent veto when the threshold is met. An incomplete description or no assessable requirements leaves the score unverified.
- A mandatory degree requires a supported qualifying degree or an explicitly accepted alternative that the candidate meets under the current degree policy. Studies alone do not prove completion.
- Apply only explicitly configured, evidence-backed limited-experience constraints. A duration above a supported limit may exclude unless a stated accepted alternative is met; unspecified duration or a preference does not automatically trigger that veto. CV omission does not establish limited experience.

Use only actual sourced confirmations for version-specific experience. A general capability confirmation does not prove years on an individual release or unrelated tools. Never invent degree completion, proficiency, tools, rates, availability, dates or titles.

Verify role/capabilities, current geography/work path, freshness, exact response route and newness independently. High fit cannot offset another failed gate. Read current private `work_location_policy` and current eligible countries separately from saved freshness. Retain exact `work_eligibility` evidence: paired opportunity ID/listing URL, actual ad or verified linked form, aware observation time, nonblank evidence, full-ad review, country/work-path scope, authorization basis and assessed constraints. Evidence for a different country or path cannot qualify.

Apply explicitly selected exclusion conditions to supported mandatory foreign visa, permit, right-to-work, residency, relocation or office-base requirements. Sponsorship does not remove a visa requirement. Unknown, ambiguous or contradictory conditions stay outside recommendations. Publisher country, payouts, time-zone overlap and remote/freelance labels establish neither eligibility nor legal status. Supported optional alternatives remain separate. Absence of a condition in the full ad is limited evidence, not employer confirmation. Do not invent citizenship, permits, salary floors, commute limits, home-working days, clearance or relocation preferences.

## 4. Cover every relevant source set

Build a private coverage ledger from current registries and resolved source selection. Inventory is separate from sources actually checked. Factual catalog/provider names do not make a geographic or technology route applicable to this candidate.

### A. Employers, suppliers and local boards

Search relevant employer/supplier career pages and exact vacancies for the configured geography and role families. Include public recruiting posts as well as job-board listings where selected and authorized. Trace board/recruiter discoveries to the exact employer or supplier requisition where possible. A suppressed requisition does not suppress every role at its employer. Choose local-language and regional sources from explicit settings, not the origin of this project.

### B. Maintained employer boards and Techmap

Read shared `sources/employer-boards.json`, [employer maintenance](sources/EMPLOYER_SOURCES.md), private overrides/observed health and any explicitly selected supplemental directory. Before bulk-opening ATS landings, consult applicable documented `manual_routes` in `sources/manual-discovery.json`; use the recorded working URL/method first, subject to current evidence. Keep registry/tenant IDs and historical API health unchanged. Derive the actual inventory and enabled/applicable subset; do not turn the bundled 288-board snapshot or provider counts into a permanent coverage claim. Prioritize likely matches to configured capabilities, then continue remaining relevant boards through authorized public pages/search.

Include every configured Techmap category in planning, with separate discovery provenance. Inspect relevant titles even when a feed lacks full descriptions. An import, feed read or old health check does not verify a current vacancy. Preserve Itai Ahiraz/israel-job-search and Techmap attribution when using their data.

### C. Remote employment and contracts

Use applicable selected channels such as Himalayas, Remote OK, We Work Remotely, Jobicy, Remotive and identifiable Braintrust opportunities. Verify complete country, engagement and time-zone conditions. Remote/region labels, an ambiguous country abbreviation or platform payouts alone do not prove eligibility for this exact role from the configured location. Seek explicit supported terms without conflicting exclusions. Source API delay does not automatically describe website or original-employer delay.

### D. Paid client projects

Use the complete maintained `sources/opportunity-sources.json` catalog and project/platform-selection references. Derive its current inventory dynamically and preserve original identities. Search concrete briefs through applicable selected marketplaces, including XPlace, Upwork, Freelancer.com, Freelancehunt, PeoplePerHour, Workana, Freelancermap and Guru; FL.ru and Codeur additionally require supported language/country/payment applicability.

For Lemon.io, Proxify, Toptal, Malt, YunoJuno, Contra and Braintrust, inspect exact accessible or supplied client opportunities within current authorization. Fiverr needs an identifiable buyer request. Enrollment, generic screening, profiles, completed work, reviews and developer-recruitment pages are not opportunities. If membership, personal feeds or private matching are unavailable, record that once and continue independent sources. Do not create accounts, read mailboxes or fetch private feeds to unlock them.

Use current acquisition routes rather than historical API rankings. An unavailable API does not eliminate accessible public pages. Follow relevant newly discovered employer/ATS/project sources when they can add distinct leads, retaining provenance without turning the search into registry maintenance.

## 4a. Selected manual channels and bounded recovery

Read [manual discovery](sources/MANUAL_DISCOVERY.md) and `sources/manual-discovery.json`. Use Arc roles and exact HN hiring comments when selected and applicable. Keep comment ID/time separate from monthly thread date; independent HN job stories are a separate lane. Omit dead/deleted items and preserve exact evidenced employer/requisition aliases. Scalable Path/X-Team/Gun.io require actual roles or supplied client matches; admission is separate. Guru's historical API-documentation limitation does not negate public project/quote navigation. Do not enroll, authenticate, send quotes or spend credits.

Scoped historical URLs remain references. Apply explicit current country/capability criteria before recommending a filtered route; unknown or mismatched criteria do not inherit the original candidate's selection. A source-planning alias or acquisition relationship never merges opportunity identities.

Record each attempted **URL plus method** (`public_page`, `isolated_browser`, `public_search`), resolved redirect URL, query/page scope and actual result. Preserve functional `?embed=js`, `?ashby_jid=...` and requisition parameters; remove only recognized tracking parameters. Extractor failure does not consume a distinct authorized isolated-browser attempt at the same URL. Legacy URL-only attempts describe public-page attempts, not all possible methods.

Use the applicable documented working route first. If real cards appear, follow pagination instead of restarting elsewhere. For an initial browser loading shell/footer, allow one bounded readiness wait of at most 20 seconds and at most two further DOM reads for actual content, explicit empty state, login or settled error. A remaining shell is partial/unknown, never empty. Do not retry snapshots indefinitely.

After failure, try at most three documented applicable alternatives, each URL/method pair once, then bounded per-employer exact original-ad discovery within the authorized coverage plan. Keep attempted-pair/redirect evidence to stop career-page/failed-iframe loops. Require actual role/detail links for board recovery; a reachable corporate page alone is insufficient. A mixed multi-employer query is discovery, not a separate check of every employer. Record each employer's result and continue independent lanes. Never bypass controls or guess tenants/APIs. The offline planner supplies bounded suggestions; its output is not proof that any URL or method was executed.

The following are historical public route references retained from the pinned source prompt dated 2026-11-26, not new checks or default source selections. Use them only for an applicable selected employer, recheck current content and retain conflicting earlier observations separately:

| Employer | Documented route/method | Limit |
| --- | --- | --- |
| CodeValue | `https://www.codevalue.com/career` | Singular career path; exact vacancy still needs verification. |
| CommIT | `https://www.comm-it.com/commit-jobs` | Empty categories do not establish an empty board. |
| Oktopost | `https://jobs.lever.co/oktopost`, isolated browser | Extractor and browser outcomes can differ. |
| Finout | `https://jobs.ashbyhq.com/finout`, isolated browser | A shell is not inspected inventory. |
| NESS | `https://www.ness-tech.co.il/careers/`, isolated browser | Regional source, subject to configured applicability. |
| The Trade Desk | `https://careers.thetradedesk.com/jobs`, public page | Reported totals/pages are not the count of inspected cards. |
| Candex | `https://jobs.ashbyhq.com/candex?embed=js`, isolated browser; `https://www.candex.com/site/careers/` | Bare-root failure and embedded success are distinct observations. Preserve actual observed `ashby_jid` detail parameters; never fabricate IDs. Talent pools are not vacancies. |

X-Team may show a loading message before roles appear. Recheck dates, listing details and response routes during the invoked run. Follow remaining pages when authorized; first-page diagnostics are only partial coverage. These references do not update catalog/tenant identity or collector health.

HTTP success, line count, shell, blank frame, generic login or access error is not an inspected list or zero opportunities. `checked_empty` requires explicit empty evidence for the completed selected scope, without contrary role links or remaining pages. Empty categories do not erase roles elsewhere. Store `checked`, `checked_empty`, `partial`, `blocked` and `not_attempted`. Current research coverage is separate from collector health.

## 5. Search broadly, then qualify precisely

Run separate searches for every selected role family in the configured search languages. Search individual capability terms and combinations; do not require every capability in the title/snippet. Use query families derived from explicit parameters, for example:

- `{role_title_variant} {capability} {configured_geography}`.
- `{second_capability} {accepted_role_alternative}`.
- `{selected_leadership_or_analysis_family} {technical_context}`.
- `{client_outcome} {capability} {contract_or_project_terms}`.
- Equivalent supported terms in each configured language.

Expand relevant title/spelling variants, including consultant and contract terminology when selected. Do not apply a generic manager/lead/analyst blacklist or blanket `-degree` filter that hides preferred-degree/equivalent-experience roles. Query breadth does not relax the final criteria.

Use native recent/date filters and public search recency filters for discovery. Follow available pages, categories and result batches; first-page results and capped feeds do not prove exhaustion. Recover moved/blocked listings with employer plus exact ID. When duplicates dominate, change source, role wording or outcome terms instead of repeating the same query. Keep CV contents and private contact details out of queries and uploads.

Stage the work: broad discovery and early identity/hard-mismatch checks; full description, fit, freshness, geography and route verification; then tailored drafts. Do not draft recommendations for unqualified leads or let one inaccessible site stall other lanes.

## 6. Verify freshness and application/proposal routes

Require original publication or a genuine opportunity-specific refresh/repost inside the applicable fixed window. An older original can qualify through supported recent refresh; retain both events and identify the qualifying one.

Record raw date wording, event type, source URL, observation time, precision and time zone. Metadata must belong to the exact listing. Crawl/index/discovery time, feed updates/addition dates, generic page modifications, deadlines and snippets alone are not publication/refresh evidence. Do not automatically promote Greenhouse `updated_at`, Comeet `time_updated` or Techmap updates into genuine reposts.

For date-only or relative wording, use its supported interval; the whole interval must fall within the applicable saved bounds. Seek a precise original source if the interval overlaps the cutoff. Missing, conflicting or future dates remain unresolved; never invent a timestamp or widen a window.

Open the exact listing and follow Apply/Submit proposal far enough to verify the destination's ID or exact title plus employer/client. Recheck qualifying routes during this run; route evidence older than 24 hours at evaluation cannot establish current availability. Record actual URL/navigation, identity linkage, status and check time. Preserve exact linked-form provenance; a project proposal form does not become an employment application form.

A readable listing, API apply URL, generic login, talent pool, unrelated form or email-only employment invitation does not pass. A login barrier needs independent current evidence that this exact opportunity accepts responses. Label it **Login required; not verified beyond this point**, translated faithfully to the configured report language. Do not imply authenticated-form inspection.

Record message-field visibility and observed length limits, or their absence/unknown state. For projects retain outcome, scope/deliverables, language, location/time zone, stated duration/deadline, budget/currency/hourly-or-fixed basis, proposal availability and visible fees/credits/membership restrictions. Unpublished budget is unresolved commercial information, not automatic exclusion. Missing credits, paywalls or unresolved account/country/payout conditions stay explicit; a login exception does not clear them.

If education is unstated after a complete read, report: **No degree requirement was stated in the full advertisement; this is not employer confirmation.** Ambiguous education stays unresolved; studies do not prove a completed degree.

Stop before entering personal data, autosaving external-form text, uploading, sending, paying or accepting terms. Use only a fresh isolated hidden/headless session, never personal desktop/windows/tabs/profile/cookies/credentials. Respect access controls and continue elsewhere when evidence is unavailable.

## 7. Reconcile history without losing legitimate new leads

Recheck both private canonical history files immediately before finalizing, including concurrent changes. Deduplicate by employer/ATS/requisition or marketplace/project identity, evidenced aliases and identity-bearing URLs. Preserve functional job-ID parameters. Investigate supplier cross-posts of the same end-client requirement; count one underlying opportunity once. Possible duplicates remain unresolved; different requisitions at one employer can remain distinct.

Reassess promising previously discovered but never reported leads under this new run, retaining IDs and earlier decisions. Reported, applied, explicitly declined or suppressed opportunities stay excluded despite a new URL/refresh. A past technical/freshness failure is not automatically a permanent user rejection. Preserve actual reasons and new evidence.

Read all exact standing suppressions and equivalent aliases from current private canonical history and explicit user instructions. This public prompt contains no personal exclusion list. Never suppress an entire employer or marketplace because of one requisition or an unresolved generic mention.

If history is unreadable, continue useful discovery with newness unverified; do not replace missing history with an empty file or count those leads as confirmed new.

## 8. Work through coverage and preserve progress

Only when current delegation policy permits research workers, assign non-overlapping batches with the same fixed windows, criteria, history and browsing/no-submission limits. No nested delegation. Use one canonical JSON writer to avoid conflicts; otherwise process lanes sequentially. This workflow does not override model, cost, worker-count or current scope limits.

For each source/lane retain queries/navigation, pages/cursors/date coverage, observation time, inspected leads and coverage status. Failure is unknown coverage, not zero jobs. Preserve progress after source batches and provide concise updates without stopping for questions.

Do not stop merely at the minimum, after one dry source or after reading a registry. Complete accessible planned lanes and promising follow-ups within any explicit cap, then perform a focused gap-filling pass over undercovered tracks/sources. Stop at completed bounded coverage or a real tool/access/resource limit. State what remains; never claim a mathematically maximal or exhaustive internet search.

## 9. Deliver actionable results directly in chat

Use the configured report language and the supported listing/recipient language for each draft. Start with exact saved windows and verified distinct totals by employment, contracts and concrete paid projects. Give freshness-band counts appropriate to the resolved window when supported/requested; do not inherit fixed bands from a different-duration example. Per-source counts overlap and cannot be summed as unique opportunities.

Provide a compact ranked index and a card for every qualifying opportunity within the resolved delivery scope. Rank using evidenced fit, practical response route and freshness without inventing preferences. Each card includes:

- Exact title, requisition/project ID, employer/client and engagement type.
- Listing URL and exact verified application/proposal URL or observed navigation.
- City/country and on-site/hybrid/remote/unknown format, with current country/work-path eligibility evidence.
- Fit M/N and percentage, main supported requirements and material gaps.
- Degree state and other eligibility/access conditions.
- Original publication and genuine refresh/repost evidence, the qualifying event and route-check time in the configured time zone.
- Message-field visibility and observed limits.
- Project outcome, scope, budget/payment basis, duration/deadline and material proposal conditions where applicable.
- A short tailored **Draft — not sent**, following [recipient contracts](skills/workhunt-apply/references/recipient-drafts.md): employer requirement/evidence/contribution; client result/bounded paid deliverable/acceptance; agency exact vacancy/team contribution. A network/admission draft is separate source-access material, never a qualifying card. Keep selected portfolio relevance and individual contribution/disclosure evidence. Unresolved placeholders or factual/terms reviews remain not-ready. Never claim an attachment, sending, unsupported capability, unconfirmed rate or availability. CV selection is not attachment.

After verified cards, show a separate compact promising-but-unverified table for strong unreported leads with supported fit of at least 75% that lack freshness, route, eligibility or identity resolution. Name missing evidence and the next check. They contribute zero to the verified count and receive no recommendation letters. Excluded, stale and suppressed records belong in the evidence/exclusion summary.

Finish with actual coverage, access limits, exclusion/duplicate counts and unfinished lanes. Report the real count and shortfall against the resolved minimum. This explicit manual invocation receives a result even at zero; notification silence does not apply. If output limits prevent every card, preserve the full private report, use numbered chat batches where possible and identify exactly what remains undelivered. Do not silently truncate.

## 10. Save evidence and verify the final count

Merge assessed opportunities, observations, source aliases, requirement evidence, unsent drafts and honest decisions into `.workhunt/data/jobs.json` under this new run. Preserve previous decisions, timestamps, provenance and unrelated/concurrent changes. Keep applied/exclusion history intact; create no submission events from research. Legacy `applications.json`, `manual-opportunities.json` and `reviews.json` are read-only compatibility inputs, not new destinations.

Save the exact run policy, source/query coverage, qualified IDs/counts, unresolved leads, blockers and continuation state. Keep found, qualified, reported, prepared, uploaded and submitted states distinct. Mark reported only after actual chat delivery; a saved draft/report is neither delivery nor an application.

Validate JSON and read back the exact run ID, fixed bounds, source windows, unique qualified IDs, counts, exclusions and aware timestamps. Use the real runtime schema; never manufacture evidence flags to make a gate pass. Local validation is not independent proof of current availability. Reconcile the delivered cards with final history and verified IDs. Do not substitute code changes, a plan, raw links or a JSON file for the completed authorized search.
