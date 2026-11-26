# AGPL-3 release preparation

This directory's historical name is not a GPL license declaration. Project-owned Workhunt content uses **AGPL-3.0-only**.

The implementation follows the approved five-part preparation plan: exclude private material and secrets; keep retained code commentary in English; generalize and synchronize English skills/guidance; replace embedded candidate facts with empty shared templates and private configuration; and add a provenance-aware CV-to-profile skill.

The release repository was initialized separately; no private source `.git` directory or old commits were imported. During finalization, an external actor created root commit `d3edb1856acac1344d8e35281d1d1e0cfbc40f64`, renamed its branch to `main`, and configured an `origin` remote. This task preserved that root and `main` reference, then created a new `codex/agpl3-release` branch carrying its uncommitted final corrections. The source workspace remained read only for this task. A clean export without `.git` is separate from repository publication.

The captured input revision was `b4c8487b1bb4c8ae474a739232ebacaeaceca834`; the original planning baseline was `a0d921b70622a3f2f5acb6d5f955a9d23bd330ed`. Source work changed concurrently after capture and is not silently included in this release. Reusable uncommitted runtime modules/tests were captured with per-file hashes outside the release.

See [validation](VALIDATION.md) for actual checks, independent synthetic skill evaluation, fixes and limitations. The source subsequently advanced independently to `c3b6729bd406400e4cafa082dc2b5c054c84e440`; those concurrent changes were not imported into the captured release snapshot. This task performed no push or publication; external publication status was not established. The inherited Job Hunt Kit's sharing statement and lack of explicit AGPL relicensing permission remain described in [third-party notices](../THIRD_PARTY_NOTICES.md).
