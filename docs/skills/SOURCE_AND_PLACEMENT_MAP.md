# Maintained sources and provider placement

The twelve focused packages are maintained in `docs/skills/workhunt-*`. Their provider copies are generated under `.agents/skills/`, `.claude/skills/` and `.kiro/skills/` by `tools/refresh_workhunt_references.py`.

Four runtime packages are maintained in `skills/`: `workhunt-search`, `workhunt-cv`, `workhunt-apply`, and `workhunt-configure-profile`. Profile setup is the fourth runtime package and is registered in `tools/install_workhunt_skills.py`. Provider repository copies include all sixteen packages.

Shared authorities are `templates/`, `JOB_SEARCH_PLAYBOOK.md`, `docs/skills/WORKHUNT_CONTEXT.md`, `docs/skills/JOB_TRACKING.md`, and `sources/opportunity-sources.json`. Refresh copies only these empty/generic authorities into self-contained package references/assets, then synchronizes provider copies. It never reads `.workhunt/` or a root populated profile and never creates private runtime records.

The installer requires `--home PATH` and installs the sixteen packages into `.agents/skills`, `.claude/skills`, `.kiro/skills`, and `.gemini/config/skills` beneath that explicit directory. It verifies content, preserves unrelated files and rejects local modifications. An isolated test installation proves those file placements only, not discovery by a user's application or a personal ChatGPT installation.

Completed CV/profile/history/output records always stay under the selected workspace's ignored `.workhunt/`, outside packages. Relative project links are repository conveniences; installed skills use their bundled generic context/playbook/tracking/catalog copies.
