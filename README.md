# Workhunt

Workhunt provides evidence-based job and paid-project research skills, an optional public-listing collector, and private local review records. Discovery is not an application or a verified match.

Project-owned code and documentation are **AGPL-3.0-only**. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md). The original supplied Job Hunt Kit's sharing statement is not explicit AGPL relicensing permission; that provenance limitation remains documented before public distribution.

## Special thanks

Thank you to the people who shared resources that helped make this project possible:

- **[Itai Ahiraz](https://www.linkedin.com/in/itai-ahiraz/)** — for creating and sharing [israel-job-search](https://github.com/ahiraz/israel-job-search), a valuable resource for Workhunt's Israeli job-search integration.
- **[Shahar Bar](https://www.linkedin.com/in/bshahar/)** — for creating and sharing the **Job Hunt Kit** for Claude Code, a foundation for Workhunt's local job-search workflow. Workhunt's collector is adapted from his kit, which also provided a workflow for setting up a profile, reviewing matches against a CV, retaining scan history, and displaying results locally. See [detailed attribution](THIRD_PARTY_NOTICES.md#shahar-bar-and-the-job-hunt-kit).

## Private setup

Use [workhunt-configure-profile](skills/workhunt-configure-profile/SKILL.md) with a CV you supply or explicitly select. It maps supported facts and explicit preferences into `.workhunt/profile.json`, keeps provenance/conflicts in `.workhunt/profile-evidence.json`, and prepares a private summary. Shared [templates](templates/profile.template.json) stay empty. No default identity, stack, geography, degree, skill tenure or enabled source is supplied.

The CV should stay outside this repository. `.workhunt/` is ignored and contains all populated profiles, histories, runs, drafts, selected CV references and generated pages. Ignore rules are not permission to publish that directory. Do not import private Git history into a public repository.

## Local use

Python 3.11 or newer is supported. `requirements.txt` supplies IANA time zones on systems lacking a time-zone database. Dependency installation is a separate user action.

```console
python skills/workhunt-configure-profile/scripts/configure_profile.py . --initialize
python skills/workhunt-search/scripts/scan.py . --fixtures /path/to/synthetic-listings.json
python skills/workhunt-search/scripts/render.py . --fixture
```

Initialization creates empty private copies; it does not authorize or enable scanning. Complete evidence and explicit search settings first. A valid profile needs configured role/title/capability patterns, country identifiers, location pattern, time zone, language and capability keys. Empty or match-all patterns are rejected before network access. `--network` is an explicit opt-in for an authorized public search; fixture mode is offline. Source discovery is disabled until explicitly selected.

Review exact listings and routes using [the playbook](JOB_SEARCH_PLAYBOOK.md). The collector never applies. It retains full text and separate date meanings; qualification requires independent fit, role, capabilities, geography, education, route, freshness and history evidence. Source failures never prove closure.

```console
python -B -m unittest discover -s skills/workhunt-search/tests -v
python tools/refresh_workhunt_references.py --check
python tools/install_workhunt_skills.py --home /explicit/sandbox/home
python tools/install_workhunt_skills.py --home /explicit/sandbox/home --check
```

The installer requires a destination and refuses unowned or locally modified conflicts. It installs twelve focused skills plus four runtime skills and shared empty references into supported provider roots. It never chooses the current user's home implicitly. See [source and placement map](docs/skills/SOURCE_AND_PLACEMENT_MAP.md).

## Release preparation

[Validation](PrepareToGPL/VALIDATION.md) records actual checks and limitations. `tools/export_release.py DESTINATION` exports a reviewed tracked inventory to a new directory without `.git` or ignored/private files; it refuses an existing destination. Publication, push, account connection, applications and outreach are separate actions.
