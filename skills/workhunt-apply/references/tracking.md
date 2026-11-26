# Private opportunity and application records

Use `.workhunt/data/jobs.json` for `opportunities` and `search_runs`; use `.workhunt/data/applied_jobs.json` for canonical `records` and unresolved historical mentions. Initialize empty histories only when the user confirms this is a new history or existing history has been migrated; absence is not proof of no prior applications.

Each opportunity preserves source/employer/project/requisition identity, aliases, full description evidence, location/work mode, publication events, route check, requirement score, decision, original discovery and later observations. Runs store fixed start/end/timezone, requested minimum, actual qualified count, shortfall and coverage failures. Preserve historical bounds.

Suppression and previously reported state survive reposts and URL changes until explicitly changed. Match IDs in provider/employer context, follow explicit aliases transitively and keep uncertain duplicates out of new-result counts. Do not collapse distinct requisitions. Read before search and again before report; merge observations without replacing prior review/submission provenance.

Local packet preparation is not submission. Submission events require actual evidence and aware timestamps. Keep user-reported or historical assertions labeled; do not promote them to independent verification. An upload is not submit; a receipt is not an interview. Preserve exclusions separately from submission status. `submission_events` and `submission_snapshots` are append-only private evidence, including preserved flat legacy records. Display the latest valid event while retaining independent ever-applied, ever-reported and suppression facts. A later upload cannot erase an earlier valid application. Persist complete explicit alias bridges through save/reload without overwriting original assessments.

Private optional files are `.workhunt/reviews.json`, `.workhunt/applications.json`, `.workhunt/manual-opportunities.json`, `.workhunt/cv-manifest.json`, and generated `.workhunt/runs/`. Runtime helpers do not publish or send them. A local JSON validation check is not live provider verification.
