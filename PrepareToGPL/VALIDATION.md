# Release candidate validation

## State and scope

Implementation and local QA performed on 2026-11-26. This is a separate repository on `codex/agpl3-release`, with no inherited private Git history. Parent review, clean export and any commit are pending at this worker handoff. Nothing was pushed or published. No application, message, account connection or dependency installation was performed.

The sole implementation worker's accepted work order selected `requested_model=gpt-6-astra`, `requested_reasoning_effort=xhigh`. Exact runtime model and effort metadata were unavailable. `mode_verified_from_work_order=true` proves the accepted request only; no runtime identity claim is made. No substitution was requested or observed. The worker did not delegate.

## Applied changes

- Canonical AGPL-3 license, English entry guidance and third-party attribution.
- Empty profile/evidence/summary contracts, ignored `.workhunt/` for populated facts, history, source health and output, and no default-enabled discovery sources.
- Private profile validation before network access; restrictive role/capability/location patterns; configured geography, time zone and language; no embedded candidate suppressions or technology-duration limits.
- Exact 75% scoring, separate freshness/route/history/geography gates, degree evidence and explicit equivalent-experience policy, preserved identity/submission evidence, and private rendering/packets.
- Twelve focused and four runtime skill packages, including CV-to-profile setup. Shared English references and empty assets are synchronized into three repository provider roots; installer supports four explicitly selected roots.
- All 23 opportunity-source IDs and dated access/terms limitations retained. Personal ranking/query examples removed. Populated employer registries and original source documents are excluded; import compatibility and attribution remain.

## Executed checks and repairs

The retained source inventory was selected explicitly rather than copying the private repository. Root CVs and derivatives, private profile/history, output, temporary files, source `.git`, populated registries and private drafts were never copied into the target. The source revision at reusable-file capture was `b4c8487b1bb4c8ae474a739232ebacaeaceca834`. The capture manifest contains hashes for sixteen original reusable files outside the release. Independent source edits continued afterward; this is not a claim that every later source change was transferred.

The main offline command was `python -X utf8 -B -m unittest discover -s skills/workhunt-search/tests -v`, using an existing Python environment with the already-installed `tzdata` dependency. It completed **91 tests, OK**, exit 0. These are test executions, including inherited test methods, not 91 independent reviews or agent passes. No live provider or browser verification is claimed.

Failures were retained in external local logs: the first global-Python run had 46 errors because that interpreter lacked `tzdata`; no dependency was installed. The next run exposed a synthetic fixture missing its explicitly configured language alias; the fixture configuration was corrected. A later two-profile fixture accidentally reused one listing URL for two IDs and was deduplicated; the fixture was corrected to distinct URLs. No matching, privacy or evidence gate was weakened to pass a test.

The release tests exercise unconfigured/empty/match-all patterns before requests or output; missing private profile despite a populated legacy root file; two explicit capability/geography/time-zone profiles; shared-template byte invariance; blocked output/source-health path escape; degree-policy allow/deny and completed versus unfinished qualifications; provenance-preserving CV mapping, overlapping interval union, unknown skill duration and conflicting dates; initialize-then-populate and overwrite refusal; existing history preservation; safe refresh; and isolated installs with unrelated-file preservation and modified-file conflict refusal.

The synthetic CV-like text was created inside a temporary directory, read into a structured evidence mapping and removed with that directory. Its overlap calculation was 1,096 supported non-overlapping days. The unfinished qualification remained incomplete, unspecified skill duration remained null, both conflicting date claims remained in the evidence ledger, and absent search preferences left the output unconfigured. No completed synthetic CV document or populated synthetic profile is bundled. This is a deterministic mapper exercise, not yet an independent agent forward evaluation of the skill.

Initial reference inspection found broken relative links in derived shared-reference copies. Refresh was repaired to produce package-local links and bundle required source-guide/notice references. The subsequent readback found only this validation file's then-pending README link; this file now supplies that destination. Final parent link verification remains pending.

After the reference-copy repair, `tools/refresh_workhunt_references.py --check` returned 16 packages, zero changed files, exit 0. The release-focused unittest discovery (`-p test_release.py`) then ran 25 tests, OK, exit 0; this overlaps the earlier 91-test suite and is not an additional independent review count. The installed skill-creator `quick_validate.py` returned `Skill is valid!` for `skills/workhunt-configure-profile`, exit 0. This validates its package syntax, not semantic agent behavior.

The parent independently inspected the pre-validation 841-file tree: no binary files or recognized candidate/private-path/secret patterns, all 23 catalog IDs preserved, and 612 canonical/provider file-pair byte comparisons with zero mismatches. Those comparisons cover 16 packages across three repository provider roots. The checks are bounded inventory/pattern evidence, not a guarantee against every possible unknown secret.

At that readback, the candidate contained 841 non-Git ordinary UTF-8 text files before these two preparation documents were added: 572 Markdown, 66 text, 79 JSON, 53 Python, 64 YAML, 4 HTML and 3 extensionless files. All Python files parsed. Code comment/docstring inspection found no Cyrillic or Hebrew prose; Markdown guidance likewise had none. Intentional Hebrew search/provider literals and Unicode test data remain distinct from commentary. Candidate-identity/private-path scanning found no original personal identifiers. Secret-pattern inspection found eight credential-URL matches: two negative synthetic URL tests repeated across the canonical package and its three provider copies. They are test strings, not actual account credentials. No actual secret key, connection string, CV or populated private record was found in the inspected retained inventory. These checks reduce risk; they do not establish legal rights to third-party content.

## License evidence

`LICENSE` was downloaded unchanged from `https://www.gnu.org/licenses/agpl-3.0.txt`: 34,523 bytes, SHA-256 `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`. The parent separately compared official SPDX AGPL-3.0-only text: it matched after whitespace and HTTP/HTTPS normalization; that is semantic corroboration, not byte identity with SPDX. Project-owned declarations use AGPL-3.0-only. Canonical AGPL references to GPL are retained.

The supplied Job Hunt Kit credits Shahar Bar and says "Free to share." The parent inspected the original document locally. This supports sharing but is not explicit AGPL relicensing permission for inherited portions. Attribution is preserved in the collector and notices; public-distribution licensing clearance remains unresolved. The MIT upstream notice is preserved. Techmap data is not bundled and its ODbL attribution remains in adapter output.

## Remaining final checks

Parent independent review, fresh skill forward evaluation, final synchronized inventory/reference checks, any authorized commit, and a separately inspected clean export without `.git` remain pending at this handoff. Do not describe export or publication as completed from this record. No personal application installation or application discovery by a UI was tested; isolated placement is the evidence scope.
