# Third-party provenance and notices

Project-owned Workhunt modifications and guidance are licensed AGPL-3.0-only. The canonical project license does not replace upstream rights or provider terms.

## Shahar Bar and the Job Hunt Kit

**[Shahar Bar](https://www.linkedin.com/in/bshahar/)** is the creator of the **Job Hunt Kit**, supplied as a 17-page PDF for setting up a local job-search workflow with Claude Code. The kit is a foundational source for Workhunt's local search workflow. Workhunt's collector explicitly acknowledges adaptation from it in `scan.py`.

Credit covers the kit's profile setup, public employer-board scanning, review of matches against a CV, saved scan history, and local HTML results workflow. Appendix A supplies five files:

| Original kit file | PDF pages | Contribution documented in the kit |
| --- | --- | --- |
| `SKILL.md` | 5-6 | Profile questions, scanning, CV-based review, saved picks, reporting, and privacy guidance. |
| `scan.py` | 7-10 | Public Greenhouse, Ashby, Lever, and Comeet collection, profile filters, and per-run outputs. |
| `render.py` | 11-12 | Local results generation and comparison with earlier runs. |
| `page.html` | 13-16 | A filterable results page with new-role indicators, changes between scans, and per-role status controls. |
| `profile.example.json` | 17 | A configuration example with preferences, filters, extra boards, and search links. |

These references identify the supplied source material. Workhunt's current code and guidance include adaptations, reorganized modules, additional verification rules, and separate integrations.

The source identifies its author on page 2: "Made by Shahar Bar." It also states "Free to share." The kit separately credits **Shahar Polak** for the [who-is-hiring company directory](https://www.shaharpolak.com/who-is-hiring); that source credit is retained here.

The supplied PDF itself is not bundled in this repository. The sharing statement is positive evidence of permission to share; no explicit AGPL relicensing permission was found. This remains a licensing limitation requiring resolution before representing every inherited portion as AGPL-cleared.

## Itai Ahiraz and israel-job-search

**[Itai Ahiraz](https://www.linkedin.com/in/itai-ahiraz/)** created and shared **[israel-job-search](https://github.com/ahiraz/israel-job-search)**. Workhunt directly reuses its pinned employer directory and draws on its reference implementation for combining employer-board collection, Techmap discovery, and merged results. The inspected upstream revision is [`7e3a2a8a21c7bea967ddccf6812163ee45adc2f2`](https://github.com/ahiraz/israel-job-search/tree/7e3a2a8a21c7bea967ddccf6812163ee45adc2f2).

The repository now bundles the exact **288-record** upstream `data/companies.json` as `sources/upstream/israel-job-search/companies-7e3a2a8.json`: Comeet 168, Greenhouse 67, Ashby 27, Lever 12, SmartRecruiters 11, and Recruitee 3. Its SHA-256 is `a2cfbf275e043f0c133059f9aed54a226d8f682199d0d9e5713d15ffd24f657d`. The [source inventory](https://github.com/lubochka/israel-workhunt/blob/main/sources/upstream/israel-job-search/README.md) records the source URL, exact bytes, and retained notice.

| Contribution from israel-job-search | Evidence in the pinned upstream | Impact in Workhunt |
| --- | --- | --- |
| Employer directory and provider identifiers | `data/companies.json`; `jobsearch/companies.py` | The exact source records are bundled. `source_registry.upstream_board()` consumes their `name`, `domain`, `provider`, `token`, and `careers_url`, including the Comeet `uid::token` representation. |
| Provider coverage and collection reference | `jobsearch/adapters.py`; `jobsearch/discover.py` | The integration maps six provider families and adds SmartRecruiters and conditional Recruitee support in `adapters.py` and `scan.py`. The earlier Greenhouse, Ashby, Lever, and Comeet collector foundation remains separately credited to Shahar Bar. |
| Employer boards plus complementary Techmap discovery | `skills/find-jobs/SKILL.md`; `jobsearch/boards.py`; `jobsearch/techmap.py` | `scan.collect_boards()` combines explicitly selected sources. `TECHMAP_CATEGORIES` and `techmap_parse()` support the same 19 category feeds; Techmap remains separately attributed to Michael Lugassy. |
| Combined results with source information | `jobsearch/merge.py` | The upstream merge workflow informed Workhunt's combined discovery handling. `deduplicate_discoveries()` uses Workhunt's own identity rules and retains source observations, aliases, categories, and date provenance. |
| Source maintenance and personal additions | `jobsearch/companies.py`; `skills/update-companies/SKILL.md`; `jobsearch/discover.py` | The upstream separation of shared companies and personal additions is a reference for Workhunt's maintained registry. `maintain_workhunt_sources.py`, `build_registry()`, and `effective_boards()` import the attributed snapshot while preserving local overrides and recorded health. |

Workhunt uses its own skill interface and implementation. Its SmartRecruiters completeness checks, conditional Recruitee XML reader, registry state preservation, and fit/freshness/application/history verification are Workhunt adaptations and additions. This mapping credits the source data and integration reference without asserting that the upstream plugin, title matcher, or every adapter algorithm was imported unchanged.

The raw employer snapshot and a sanitized normalized shared seed are bundled. The seed uses uniform imported defaults and unverified health; no candidate priorities, private overrides, observed health or Techmap job data are bundled. Private registry updates remain explicit local actions, source switches are disabled in the shared profile, and a network scan requires direct current authorization plus configuration. The counts above describe the pinned source inventory; current board availability and open jobs require a separate live check.

**Upstream attribution chain:** israel-job-search's [Credits and sources](https://github.com/ahiraz/israel-job-search/blob/7e3a2a8a21c7bea967ddccf6812163ee45adc2f2/README.md#credits-and-sources) credits **[Amir Baldiga's jobsworm](https://github.com/baldiga/jobsworm)** for the board adapters and company list, and **[Michael Lugassy's Techmap](https://github.com/mluggy/techmap)** for the category job lists. Workhunt preserves these origins alongside the acknowledgement of Itai's integrated project and workflow.

The upstream **MIT notice is retained unchanged** at [sources/upstream/israel-job-search/LICENSE](upstream-license.txt), including `Copyright (c) 2026 israel-job-search contributors`. The personal acknowledgement of Itai accompanies that collective copyright notice. Imported registry provenance retains the upstream repository, revision, source URL, snapshot hash, and MIT attribution.

## Other sources

- [TheRemoteFreelancer](https://github.com/engineerapart/TheRemoteFreelancer) informed work-location evidence research and the current resource discovery/channel classification. The pinned [README](https://github.com/engineerapart/TheRemoteFreelancer/blob/849f6c6c3b080bfbf9cd0722e72a8cfcf5aee407/README.md) credits **Codinronan** as originator and **Andy Chase** as maintainer since 2017. HN discovery is attributed to that README (HNHIRING); Arc, Scalable Path, X-Team, Gun.io and Guru are attributed to its pinned `docs/_data/sites.csv`. Its [Unlicense at revision 849f6c6c3b080bfbf9cd0722e72a8cfcf5aee407](https://github.com/engineerapart/TheRemoteFreelancer/blob/849f6c6c3b080bfbf9cd0722e72a8cfcf5aee407/LICENSE) remains separate from Workhunt's license. Selected resource names and classification are adapted with provenance; no CSV snapshot or runtime code was imported from that project, and platform-level research is not current opportunity verification.

- The optional Techmap adapter refers to Michael Lugassy's https://github.com/mluggy/techmap. Source data is ODbL-1.0; source credit and license URLs remain in adapter output. No Techmap dataset is bundled or relicensed.
- Provider names, official endpoints, attribution requirements and historical access observations are factual reference material. APIs, account access and data retention remain subject to their own terms; this project license grants no account access or data rights.

The project LICENSE was downloaded as bytes from https://www.gnu.org/licenses/agpl-3.0.txt. Canonical license references to other GPL versions and HTTP URLs remain intact.
