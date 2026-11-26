# Recipient and stage for local drafts

Choose by the actual relationship, not just the platform name. Every draft is **Draft — not sent**. The current opportunity must already qualify for a recommendation letter. Separately requested network admission drafts stay source-access material and never increase the opportunity count. Neither drafting nor a source route authorizes onboarding or contact.

| `recipient_type` | `stage` | Required structure |
| --- | --- | --- |
| `employer` | `vacancy_application` | Exact role/ID → relevant requirement → supported example → contribution → conversation. |
| `client` | `project_proposal` | Client outcome → supported example → first bounded paid deliverable → acceptance criterion → unresolved scope. |
| `network` | `network_admission` | Specialization → representative engagements → individual contribution → supported work preferences. Do not invent a client brief. |
| `agency` | `agency_screening` | Exact opening/ID and known client → hands-on ownership → team contribution → supported example → observed next assessment stage. Do not promise fixed-price delivery. |

Use the observed recipient, language, field availability and character limit. Unknown limits are not a universal 200-character cap. Missing recipient/stage facts remain unresolved; do not ask the user or invent them. Do not promise rates, start dates, availability, relocation or skills. Draft questions for a future authorized client conversation may be retained locally; never send them automatically.

## Employer

Hello [observed team/name], your [role and ID] calls for [exact requirement]. My work on [verified example and individual contribution] is relevant to [specific responsibility]. I would welcome a conversation about contributing to [supported role outcome].


## Direct client

Your brief calls for [concrete result]. In [verified comparable example], I contributed [specific work]. A proposed first paid step is [bounded deliverable], accepted against [criterion]. [Dependency/scope item] remains to be clarified before estimating the full engagement. Relevant evidence: [reviewed sample or anonymized narrative].


## Talent network

My supported specialization is [specialization]. Two representative engagements are [verified engagement/contribution] and [verified engagement/contribution]. I am interested in [supported work preferences]. I would like to understand the network's documented matching/assessment process.


## Staffing agency

I am interested in [exact opening and ID]. My hands-on ownership of [supported example] and collaboration with [supported team context] are relevant to the client's stated [need]. I would welcome the documented next assessment step, with [unknown material condition] still unresolved.


## Portfolio handoff and attachment review

For each selected sample retain `selected_for`, `source_url`, `individual_contribution`, `evidence`, `visibility` (public/private/anonymized narrative), and any limits. Private work requires a reviewed anonymized narrative; do not attach private code or attribute team/upstream/AI work entirely to the candidate. Record what the draft actually uses, not an unrelated portfolio list.

Select one exact role/language CV through the manifest. Before any authorized upload, verify current bytes/hash, readable text and rendered layout, correct language/role, factual reconciliation and absence of unresolved material claims. Hash match is not content/visual review. Keep actual filename/version, upload evidence and submission evidence separate.

None of these templates says a CV is attached. Such wording is allowed only after an actual observed upload for this exact opportunity and selected file, within separately authorized sending scope. Selection, local preparation or a filename is not attachment evidence. `drafts.py::prepare_draft` records missing content/recipient evidence, observed field limits, portfolio handoff and attachment-quality gaps. It does not send or silently repair claims. Packets use this helper automatically; `drafts.py WORKSPACE --input request.json --output drafts/local.json` also supports a local network draft without inventing an opportunity. Draft readiness is not sending permission or independent fact verification.

Readiness also requires an attributed `claim_review` covering experience, rates/availability/hours/start date (supported or omitted), observed language and submission wording. Known placeholder patterns and unsupported attachment/submission phrases are flagged automatically. These are bounded review aids, not semantic proof of every statement. Keep unresolved wording visibly not-ready; `ready_for_use` never authorizes an external action.

Standalone input and output paths resolve under the selected workspace's `.workhunt`; no configured profile is required for a network draft. Canonical records, configuration, legacy inputs, shared templates and the request itself cannot be output targets. Packets use the same reviewer.

For `attachment_intended`, the selected CV must have `file_status: hash_matches`, `ready_to_attach: true`, `content_reviewed: true`, no unresolved facts, and a content review bound to its measured hash. `attachment_quality` must name the same `version_id` and `sha256`, provide nonblank evidence, and confirm content, rendered layout, role/language and factual review. Contradictory or stale flags cannot override the manifest selection. These supplied reviews are attributed evidence, not independent semantic validation.

For an attachment claim, accept a saved canonical `uploaded` event unchanged, or legacy `uploaded_observed`, only with retained authorization, exact opportunity/current hash, nonblank observation evidence and an aware nonfuture time. Saved authorization is historical evidence, not permission for another upload or send. Upload remains distinct from submission and cannot bypass the selected-version quality checks above. A concrete paid-project client invitation may use the client contract after all normal qualification gates; generic platform invitations remain source access.
