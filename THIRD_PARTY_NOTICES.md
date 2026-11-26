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

## Other sources

- Employer registry import compatibility references https://github.com/ahiraz/israel-job-search at revision `7e3a2a8a21c7bea967ddccf6812163ee45adc2f2`. Its MIT notice is preserved at [sources/upstream/israel-job-search/LICENSE](sources/upstream/israel-job-search/LICENSE). No upstream company snapshot or populated registry is bundled. A later authorized import must preserve its notice and source provenance.
- The optional Techmap adapter refers to Michael Lugassy's https://github.com/mluggy/techmap. Source data is ODbL-1.0; source credit and license URLs remain in adapter output. No Techmap dataset is bundled or relicensed.
- Provider names, official endpoints, attribution requirements and historical access observations are factual reference material. APIs, account access and data retention remain subject to their own terms; this project license grants no account access or data rights.

The project LICENSE was downloaded as bytes from https://www.gnu.org/licenses/agpl-3.0.txt. Canonical license references to other GPL versions and HTTP URLs remain intact.
