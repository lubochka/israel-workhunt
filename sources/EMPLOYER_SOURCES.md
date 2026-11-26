# Employer source maintenance

The shared seed contains 288 public boards from the pinned MIT-licensed `israel-job-search` snapshot: 168 Comeet, 67 Greenhouse, 27 Ashby, 12 Lever, 11 SmartRecruiters and 3 Recruitee. It is separate from the 23-source opportunity catalog. Imported enabled/priority fields are uniform defaults, not a candidate's choices; health starts unverified.

The exact snapshot is [companies-7e3a2a8.json](upstream/israel-job-search/companies-7e3a2a8.json), revision `7e3a2a8a21c7bea967ddccf6812163ee45adc2f2`, SHA-256 `a2cfbf275e043f0c133059f9aed54a226d8f682199d0d9e5713d15ffd24f657d`. The [MIT license](upstream/israel-job-search/LICENSE) remains unchanged. Comeet `uid::token` values are public board identifiers from this snapshot.

Profiles explicitly enable the registry and select its shared relative path. Runtime resolution first reads a private registry at that path if present, otherwise the selected shared release seed. Private `.workhunt/sources/employer-overrides.json` supports board corrections/additions; copy the empty [override template](employer-overrides.template.json). Private `source_health_file` holds actual observations and retains last-success evidence across later failures. No real observed health or candidate priorities are distributed.

Run `python tools/maintain_workhunt_sources.py --workspace PATH --snapshot sources/upstream/israel-job-search/companies-7e3a2a8.json --dry-run` for a local comparison. `--apply` writes a private registry; `--check` reports whether another import would change it. Imports preserve local metadata and mark missing upstream entries instead of deleting them. An upstream network refresh is separate, explicit work. No network refresh was performed to build this release.

Techmap exposes 19 category feeds when explicitly configured. Its title-only rows remain provisional discovery evidence; dates retain their provenance. Public source availability never substitutes for fit, freshness, geography, exact application-route or history checks.
