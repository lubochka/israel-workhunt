# AGPL-3 release preparation

Project-owned content uses **AGPL-3.0-only**, with separate upstream notices. This legacy directory name is not a GPL declaration.

The current documentation update adds the supplied [CV setup prompt](../israel-workhunt-cv-setup-prompt.txt) unchanged and explains its deliberate use in [the setup guide](../docs/CV_PROFILE_SETUP.md) and root README. Reading, reviewing, copying or publishing this document does not invoke setup. Its instructions were not executed for this release: no actual CV, private profile or history was read or changed.

The guide distinguishes first initialization from reviewed updates to populated profiles, documents the existing helper's limits, and separates extracted facts, explicit preferences, configuration validity, CV review and permission to search. Original CVs stay untouched; tailoring, searching, test suites, installations and external actions need their own authorization. The original private repository is not a required dependency.

The public target base is `03555ac556c83ffccbfd0091ab1ca23400cdc701`. Runtime, schemas, templates, skills, 17 provider packages, source catalogs, licenses and the separately guarded [manual-search prompt](../workhunt_prompt.md) remain byte-identical to that base. See [validation](VALIDATION.md) for the newly performed documentation/export checks; the earlier 243-test full suite and 97-test export run are historical and were not repeated for this documentation-only change.

Source files remain read only. Private CVs, settings, history and source Git ancestry remain excluded. The worker stages and exports the inspected tree without commit or push; parent review/publication is authorized. Existing credits and the unresolved limit of the Job Hunt Kit sharing statement remain in [third-party notices](../THIRD_PARTY_NOTICES.md).
