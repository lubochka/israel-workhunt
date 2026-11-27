# Configure Workhunt from your CV

The [complete CV setup prompt](../israel-workhunt-cv-setup-prompt.txt) tells a Codex agent how to adapt this checkout to your evidence and explicitly confirmed preferences using the existing [configure-profile skill](../skills/workhunt-configure-profile/SKILL.md). It is a reusable document, not a completed setup or an automatic command. Reading, attaching for review, copying or publishing it does not invoke its instructions.

## Invoke setup deliberately

1. Open a Codex chat in your `israel-workhunt` checkout so the agent can read its current instructions, skills and templates.
2. Paste the **whole prompt** into that chat. Attach the CV you want reviewed, or give the exact local path to the file you explicitly select. Keep the original outside the repository by default. Do not place the CV, extracted text or a completed personal request in tracked files.
3. State that you want to run this setup. Add any already confirmed role, employment/project, location, language or source preferences you want applied. Unspecified preferences stay unknown; a CV headline, address or technology mention does not choose them.

For example, send this with the complete prompt pasted below it:

```text
Use the complete CV setup prompt below to configure this checkout privately
from the CV attached to this chat. Preserve my original CV and existing history.
Use only my explicitly confirmed search preferences; leave other settings unknown.
Do not search, install dependencies, rewrite my CV, upload or send anything.

[Paste the entire contents of israel-workhunt-cv-setup-prompt.txt here.]
```

Alternatively, replace “the CV attached to this chat” with “the CV at `<exact-local-CV-path>`” and supply the actual path privately. That placeholder is not a selected file. Optional preferences should be your own explicit choices, with their source retained; the example supplies no default stack, country, language, result count or freshness exception. An established no-questions preference remains binding.

The original `workhunt` repository mentioned in the prompt is an optional behavior reference, not a dependency. The public checkout contains the workflow needed for setup. Another person's CV, settings, source choices or application history must never become your configuration.

## First setup and later updates

The [configuration helper](../skills/workhunt-configure-profile/scripts/configure_profile.py) is **not a CV parser**. An agent must actually read the selected document with available tools and prepare the [evidence ledger](../skills/workhunt-configure-profile/references/cv-mapping.md). If extraction or layout review is unavailable, it must state what could not be read; it cannot mark unread content as reviewed or install/upload an extractor implicitly.

For a new workspace, inspect the destination before initialization. The current helper CLI supports `--initialize`, which only copies empty templates. It has no `--cv` parsing command. Its documented Python `populate(...)` function accepts an already reviewed ledger and optional explicitly selected CV. It can replace exact untouched template outputs, including those created by `initialize(...)`; it refuses existing populated profile, evidence and summary files. Shared templates resolve independently of profile existence.

For an existing workspace, inspect the current facts, decisions and manifest first and make only reviewed, schema-compatible private changes. There is no automatic merge/update CLI. Do not delete or reset populated outputs to bypass protection. Preserve unaffected fields, evidence IDs, user corrections, manifest versions, saved runs and both canonical histories. Missing history is unknown, not permission to invent an empty history.

CV registration measures the selected bytes and appends a version. It does not automatically deduplicate repeated registrations or resolve competing versions. Before registering again, inspect the existing path/hash, version, mappings and selection evidence; reuse supported existing information or make a reviewed update instead of silently adding duplicates or retiring versions.

For a specific role and document language, select exactly one appropriate current CV matching both mappings. Preserve existing role/language selections and version-specific uncertainty. If none or several match, leave selection unresolved; a filename, newest timestamp or another version's review cannot settle it. Do not assume an older conflict applies to a newly read version or that a derivative resolves it.

Recommendations documents suggest wording, not new facts. A matching hash or stored review flag records evidence claims; the packet selector does not independently verify the document's factual content or layout. Actual content and applicable layout checks must concern the exact selected version before claiming them complete. Preserve user-reported applications as attributed reports, with report time separate from actual submission time; leave the latter unknown when unsupported.

## Private outputs and truthful readiness

The [profile contract](../skills/workhunt-configure-profile/references/profile-schema.md) defines these outputs beneath the resolved private `.workhunt/` directory:

| File | Purpose |
| --- | --- |
| `profile.json` | Supported candidate facts and separately confirmed search preferences. |
| `profile-evidence.json` | Source IDs, private file/message references, page/section/line locators, conflicts, unknowns and calculations. |
| `professional-summary.md` | A supported summary with evidence and unresolved limits. |
| `cv-manifest.json` | Selected file path, measured hash/time, versions, supported role/language mappings and exact-content review status; an existing valid private `cv_manifest` pointer can select another private manifest. |

Keep originals unchanged. A private local CV copy requires an explicit choice. Inside a Git worktree, verify that private destinations are ignored **and not already tracked or staged** before sensitive writes; ignore rules alone do not protect tracked files. An explicitly chosen private workspace outside Git has no Git-ignore requirement. The [runtime contract](WORKHUNT_RUNTIME.md) explains shared-release and private-workspace resolution; no original author's machine path is needed.

Fact extraction is not preference selection. Preserve uncertain dates, conflicting titles, unfinished qualifications and unknown skill/language duration. Count overlapping supported employment intervals once and disclose imprecise or excluded periods. Do not infer permits, citizenship, desired roles, work location, availability or rates. Work-location and client-project policies require explicit sourced decisions; CV facts do not enable them.

Read back changed private files, verify evidence references and unchanged shared templates, and use the existing profile validator for offline configuration validation. Keep `configured: false` when required settings are missing or invalid; empty or match-all discovery patterns must fail before network access. Report configuration validity, CV content review, role/language selection, unresolved conflicts and permission to search separately. A valid profile or matching file hash does not prove attachment readiness, factual accuracy, visual quality or execution authority.

The prompt authorizes bounded private setup only when deliberately invoked. It does not authorize a test suite, dependency installation, collector/API probe, job search, account connection, application, proposal, message, upload, payment, schedule change or publication. No such action is needed to demonstrate setup. Any CV adaptation requires an additional explicit CV task, with an identified target, a separate private derivative and the [CV skill's safeguards](../skills/workhunt-cv/SKILL.md); the original stays unchanged.
