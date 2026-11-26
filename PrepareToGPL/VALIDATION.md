# Current release validation

## Scope and implementation

Implementation and local QA on 2026-11-26 follow plan `b45d4b173bfc22b05e0511ec32bf9af949211591` against reusable source baseline `a0561d1666188cc4f9f6a007cf2b8d9fc8046029`. Six exact reusable runtime/test files were captured read-only with per-file SHA-256 evidence outside the release (`workhunt-agpl3-manual-input/capture.json`). The delta was selectively integrated into the generic release instead of copying candidate defaults or private state. Earlier c3 integration and 5f audit-repair behavior remain covered. Private-history commit `11249588820433b422c80ea3443dec2ca86b1c10` was never imported.

The implementation worker made no writes to the source workspace. Concurrent user changes to its history files are outside this claim. Actual CVs/derivatives, filled profile/evidence/manifest/history, source observations, packet requests, run snapshots, output and source Git history remain excluded. Requested manual durations, minimums, technology choices, authorization and personal provenance are not public defaults.

The shared qualifier now uses saved source windows only when both `run_type` and `execution_context` are `manual`. Exact paired identity/URL membership, public provenance, textual evidence and an aware nonfuture observation are required for configured source exceptions. Unsupported membership uses the saved `other` window. Collector, notification, assessment and fixture contexts, including legacy scans, remain exactly 24 elapsed hours. New windows use the configured IANA zone with UTC duration arithmetic; saved bounds, policy, time zone and minimum survive later profile changes.

Renderer and packet preparation select an explicit canonical run or the active/latest saved run. A packet request may instead supply one full saved brief with valid aware bounds; conflicting selectors and malformed/empty snapshots fail without sliding to today's defaults. Resulting packet briefs and rendered membership evidence stay private. Shared profiles have empty `manual_source_freshness_hours` and `manual_freshness_policy` objects and omit `source_windows`, `window_start` and `window_end` entirely.

All earlier generic/private safeguards remain: first setup without a profile; provenance-aware CV mapping and manifest readiness; 17 portable packages; 288 public boards and 23 catalog IDs; private discoveries, canonical connected identities, append-only submission evidence, independent ever-applied/reported/suppressed facts, exact route gates, record-local SmartRecruiters failures, installer ownership and UTF-8/LF output.

The user authorizes applying the completed delta to public `lubochka/israel-workhunt` main. The starting target is previously published sanitized commit `35452602a2ac36d8395db1c01b9f61c8f15a9cb8`, retaining upstream attribution and concurrent user commits. This worker made no commit or push in this update. Final publication/readback is a separate parent action; this file does not claim it has occurred.

## Current executed checks

The full behavioral suite used the existing project Python environment without dependency installation:

```console
python -X utf8 -B -m unittest discover -s skills/workhunt-search/tests -v
```

Result: **148 tests in 70.125 seconds, OK, exit 0**, retained externally in `workhunt-agpl3-manual-suite-1.log`. This includes inherited unittest methods, not 148 independent reviews. The suite contains the preceding 134-test coverage plus 14 manual-window tests. No live provider, personal browser, real-candidate scan or external submission ran.

New coverage includes exact source membership/alias pairing, publication versus feed timestamps, fixed source anchors, unsupported-membership saved fallback, all nonmanual contexts, legacy scan recognition, malformed snapshot rejection before artifact writes, explicit/active/latest run selection, private packet snapshot persistence, and source-window page data. A Toronto daylight-saving transition proves elapsed-hour arithmetic outside the source's original zone; changing the current profile to Tokyo does not change the saved zone or bounds. The old manual-policy regression was updated to the new two-context contract, preserving collector 24-hour behavior.

The first targeted 14-test attempt had 16 subtest failures because its newly adapted synthetic `geography.eligible_from` fixture was a scalar instead of a list. Diagnosis showed freshness passed and geography failed. Correcting the fixture produced 14 passing targeted tests before the full passing suite. Both `workhunt-agpl3-manual-targeted-1.log` and `workhunt-agpl3-manual-targeted-2.log` are retained. A diagnostic used a global interpreter lacking `tzdata`; the existing project environment was then used, without installing anything. No product gate was weakened.

Parent read-only probes additionally verified a New York DST window, mixed alias rejection, saved 96-hour fallback/minimum/zone despite changed profile settings, collector rejection of a 36-hour event, and null source-bound rejection. Evidence is `workhunt-agpl3-parent-manual-probes.json`. These are parent verification, not another worker evaluation.

`tools/refresh_workhunt_references.py --check` reports 17 packages and zero changed shared files. Each provider has 257 expected generated files: **771 byte comparisons across three roots, zero mismatches and zero extras**. Generated expectations account for rewritten links and workspace resolvers. Fresh setup, isolated placement in paths with spaces, whole-install preflight, idempotence, modified/unowned protections, empty templates and safe refresh are exercised by the full suite.

The candidate inventory contains **1029 ordinary UTF-8 text files**: 611 Markdown, 70 text, 145 JSON, 128 Python, 68 YAML, 4 HTML and 3 extensionless. JSON and Python parse, local Markdown links resolve, and explanatory Markdown/metadata/Python comments/docstrings have no Cyrillic/Hebrew prose. Legitimate localized output/search literals remain code data. Workspace descriptors are unbound; shared profile and manifest invariants pass, including omission of derived window fields.

Bounded scans found no original candidate markers, private machine paths, recognized private-key/token/credential-database patterns, or binary/private paths. Eight credential-URL occurrences are two existing negative synthetic tests repeated across canonical and provider packages; these use fixture credentials, not actual secrets. Public Comeet identifiers are provenance-backed source data. Pattern scans do not prove absence of every possible unknown secret.

## Independent installed-profile evidence (earlier phase)

Before the final audit-repair delta, independent worker `/root/installed_profile_qa` exercised one retained installed-package scenario and returned `QA_REPORT.txt`, `observations.json` and `integrity.json`. It installed all 17 packages into four isolated provider roots with spaces in their paths, resolved the shared root before any profile existed using explicit/current/local-binding precedence, read the actual synthetic CV and invoked the installed configure-profile helper. It did not substitute source helper imports or access a personal application.

The scenario preserved the unfinished qualification, unresolved conflicting dates, unknown skill duration and language proficiency, and absent preferences. Supported overlapping intervals yielded 1,643 days, explicitly a partial career total, without inventing technology tenure or desired role. The private manifest measured the selected file, left unresolved role mapping/non-reviewed readiness visible, and fed packet selection. Separate copy-only controls verified missing/changed/unreviewed/conflicted/ambiguous versions stayed non-ready and previous versions were preserved; a reviewed exact-hash control did not grant upload authority. No real CV or completed synthetic CV artifact is distributed.

That evaluator observed all 1024 then-current release files and 76 shared assets unchanged, while two source history files changed concurrently. It made no writes to those source paths; causation was not established. Its first harness used a disposable context-mode directory that disappeared after a successful install; the retained scenario was repeated in persistent temporary storage. This harness issue is not a product defect. The evaluation predates the latest audit and manual-window repairs; current installed/setup regression tests are included in the current 148-test suite, but this record does not claim a second fresh agent scenario after these later repairs.

## Earlier failures and repairs retained as history

The initial generic release passed a 91-test suite. Earlier attempts exposed an interpreter without `tzdata` (no dependency was installed), an incomplete synthetic language alias, and two synthetic IDs accidentally sharing one URL. Fixtures were corrected without weakening gates. Broken derived-reference links were corrected. A separate early profile evaluator `/root/profile_forward_qa` identified a summary that did not fill the actual shared template; the helper was repaired and 26 targeted tests passed, followed by three mapper tests after punctuation cleanup. Its first assertion expected 15 rather than 71 assets; separate verification corrected that harness without rerunning population.

The expanded c3 release then passed 120 tests. Its earlier 112-test attempt exposed a synthetic title pattern that omitted the title expected by its test; the configuration was corrected. A narrow outcome test initially omitted canonical fixtures. Parent review also found a manifest pointer could collide with canonical history; manifest-specific destination/schema preflight and unchanged-input regression coverage fixed it. CRLF from local text writes was normalized in shared sources and generated packages, excluding canonical legal/snapshot bytes. These historical runs overlap current coverage and are not summed into independent-review counts.

The preceding audit-repair suite passed 134 tests in 56.426 seconds (`workhunt-agpl3-audit-suite-2.log`). Its initial 133-test attempt had 33 errors and two CLI failures from a dangling reference to the removed candidate-specific `STANDING` constant. Removing that dependency retained private suppression fields without restoring personal IDs. The earlier export also exposed CRLF in newly staged empty manifest assets; those bytes and generated hashes were normalized before publication. Those historical checks are not summed with the current suite as independent reviews.

## Licensing and source provenance

Canonical GNU `LICENSE` is unchanged: 34,523 bytes, SHA-256 `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`, originally downloaded from `https://www.gnu.org/licenses/agpl-3.0.txt`. Parent comparison with official SPDX AGPL-3.0-only text agreed after whitespace and HTTP/HTTPS normalization; this is semantic corroboration, not byte equality with SPDX. Project-owned declarations use AGPL-3.0-only.

The pinned upstream employer snapshot remains 51,486 bytes, SHA-256 `a2cfbf275e043f0c133059f9aed54a226d8f682199d0d9e5713d15ffd24f657d`, revision `7e3a2a8a21c7bea967ddccf6812163ee45adc2f2`. It contains 168 Comeet, 67 Greenhouse, 27 Ashby, 12 Lever, 11 SmartRecruiters and 3 Recruitee identities. The fresh shared seed has uniform priority 100, imported enabled defaults and unverified health; candidate choices and actual observations are private. The distinct 23 opportunity-source IDs equal the captured source catalog. No upstream refresh or live board check was performed for release preparation.

The unchanged MIT notice has SHA-256 `cb6fc171d61b87f6920220bc5c9069d31f47d9a9c9e1096e93dfe37863f29eec`. Itai Ahiraz, upstream contributor credits and Michael Lugassy's separate Techmap ODbL-1.0 attribution remain intact. Techmap job data is not bundled.

The supplied Job Hunt Kit identifies Shahar Bar and says "Free to share." The original PDF is not bundled. This is positive sharing-permission evidence, but explicit AGPL relicensing permission for inherited portions remains unresolved. Attribution and this limitation are retained; the project license does not replace third-party rights.

## Export and remaining boundary

The prior 1025-file sibling export was compared against every file in task commit `35452602a2ac36d8395db1c01b9f61c8f15a9cb8`; all names and byte hashes matched. After resolved-path and ownership checks it was preserved in a separate temporary backup. No unexpected user file was deleted or overwritten. The new sibling `workhunt-agpl3-export` has **1029 files**, with complete staged-candidate/export byte equality and no `.git`, private state or local bindings. Separate export inspection passes the same privacy, syntax, English, local-link, license/snapshot and 771 generated-file comparisons. Evidence is retained externally as `workhunt-agpl3-manual-export-proof.json`.

This validation paragraph was updated after the initial export inspection. Only its verified task-owned export copy was synchronized, followed by complete candidate/export equality and staged `git diff --check` (exit 0). No commit identity is embedded here, avoiding a circular self-commit claim. The parent will independently verify the final staged tree and public-main result.

Only preparation documentation is changed after the successful full suite; there are no post-suite behavior changes. Publication remains authorized but is not claimed for this delta. Isolated installation does not prove live host discovery, and synthetic CV mapping does not prove support for every document format. No personal account connection, application, message, dependency installation or network collector was performed by this worker.

## Work-order record

The implementation worker `/root/agpl3_executor` and each named independent evaluator received accepted requests for `requested_model=gpt-6-astra`, `requested_reasoning_effort=xhigh`. Exact runtime model/effort metadata were unavailable. `mode_verified_from_work_order=true` proves the accepted explicit requests only. No runtime identity or silent substitution claim is made. The implementation worker did not delegate; the parent scheduled evaluators sequentially under the one-worker boundary.
