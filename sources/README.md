# Source references

`opportunity-sources.json` preserves 23 source IDs and source-specific access, authentication, freshness, retention, fee and eligibility limitations. Historical observations are dated 2026-11-25 and are not live verification for this release. No provider is default-enabled. Candidate-specific ranking and example queries were removed.

Choose search queries and provider access from the private profile. Never create credentials, connect accounts, pay fees, schedule polling or send proposals from this catalog alone. An access/admission page is not a specific opportunity.

The repository includes the public [288-board employer snapshot and attribution record](upstream/israel-job-search/README.md) from Itai Ahiraz's [israel-job-search](https://github.com/ahiraz/israel-job-search), pinned to revision `7e3a2a8a21c7bea967ddccf6812163ee45adc2f2`, with its unchanged MIT notice. The [detailed contribution map](../THIRD_PARTY_NOTICES.md#itai-ahiraz-and-israel-job-search) credits the directory, provider integration reference, employer-board plus Techmap workflow, source maintenance, and merged discovery results.

The normalized employer registry, local overrides, and health records belong in `.workhunt/sources/`. The importer retains upstream provenance and its MIT notice; saving an import requires `--apply` and does not scan employers. Public identifiers and provider API contracts are not candidate facts. A populated normalized registry, Techmap job dataset, and private feed links are not bundled. Source switches remain disabled until explicitly configured.
