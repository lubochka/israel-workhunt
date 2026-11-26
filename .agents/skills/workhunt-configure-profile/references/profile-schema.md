# Private profile contract

`profile.json` is an empty shared contract until private evidence is mapped. Keep unknown scalar values null or empty and unknown collections empty. `configured` remains false until explicit search settings validate.

- `name`, `headline`, `identity`, `capabilities`, `experience`, `education`, `languages`: supported facts with evidence references. Capability `duration_years` may be null. Education `completed` is true only with evidence.
- `tracks`: user-selected keys, each with an English/internal `label`, restrictive `title` regex and nonempty `stack_all` capability regexes. Result language is separate. `search_brief.tracks` names selected keys; `required_stack` names review capability keys.
- `eligible_countries`: explicit identifiers/aliases for candidate-country checks. `location_pattern`: restrictive location regex; ambiguous abbreviations need explicit context. `timezone`: IANA name. `language`: explicit result language.
- `limited_experience`: evidence-backed technology-to-years caps only. Unknown duration must not create a cap. `degree_policy` records accepted qualifications and explicit alternative policy; per-listing `degree_status` still needs evidence.
- `preferences`: explicit work modes, relocation, availability and commercial constraints only. Unknown preferences remain null/empty.
- Source enable flags default false. `extra_boards`, directory URL and source paths are explicitly selected. Registry, overrides and health paths are relative to `.workhunt/` and must stay there. `matching_aliases` are user-confirmed regex/replacement pairs for discovery; they do not rewrite the original advertisement.
- `search_brief`: run type, requested minimum (null when not requested), optional cap and explicit capability keys. The runtime fixes the 24-hour window in the configured time zone. Saved run evidence is not current authorization.

Canonical history lives in `data/jobs.json` and `data/applied_jobs.json` beneath `.workhunt/`. Setup does not invent empty histories when an existing history is unknown. The optional helper never deletes those records and refuses to overwrite existing populated profile outputs without a reviewed update implementation.

Review fields use `geography.eligible`, `geography.eligible_from`, and supporting evidence; `degree_status` can be mandatory_met, mandatory_no_alternative (unmet), experience_equivalent, preferred, not_stated or ambiguous. A source listing alone does not supply these assessments.
