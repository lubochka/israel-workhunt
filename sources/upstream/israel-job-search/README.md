# israel-job-search source inventory and attribution

**[Itai Ahiraz](https://www.linkedin.com/in/itai-ahiraz/)** created and shared [israel-job-search](https://github.com/ahiraz/israel-job-search). This directory retains the public employer catalog used by Workhunt's registry integration and its upstream MIT notice. The [full contribution map](../../../THIRD_PARTY_NOTICES.md#itai-ahiraz-and-israel-job-search) also credits the reference workflow and implementation behind the broader employer-board and Techmap integration.

## Pinned source

- Repository: https://github.com/ahiraz/israel-job-search
- Revision: `7e3a2a8a21c7bea967ddccf6812163ee45adc2f2`
- Original data: [data/companies.json at the pinned revision](https://github.com/ahiraz/israel-job-search/blob/7e3a2a8a21c7bea967ddccf6812163ee45adc2f2/data/companies.json)
- Bundled copy: [companies-7e3a2a8.json](companies-7e3a2a8.json)
- Size: **51,486 bytes**, verified byte-for-byte against the upstream file.
- SHA-256: `a2cfbf275e043f0c133059f9aed54a226d8f682199d0d9e5713d15ffd24f657d`
- Git blob: `7ba2d24206050f933e08e0021edea4e462e97d8e`

## Catalog coverage

The snapshot contains **288 records and 288 unique provider/token pairs**. Each row supplies `name`, `domain`, `provider`, `token`, and `careers_url`.

| Provider | Board records |
| --- | ---: |
| Comeet | 168 |
| Greenhouse | 67 |
| Ashby | 27 |
| Lever | 12 |
| SmartRecruiters | 11 |
| Recruitee | 3 |
| **Total** | **288** |

These are counts of reference-board identities at the pinned revision. Current availability and open-job counts require a separate live check. The raw snapshot is input for an explicitly requested import; the sanitized shared seed starts with imported/unverified defaults, while active private registry updates and health/override records stay in `.workhunt/sources/`. Importing the source does not enable or run searches.

## Retained authorship and source chain

The upstream [LICENSE](LICENSE) is preserved byte-for-byte, including **Copyright (c) 2026 israel-job-search contributors**. Its SHA-256 is `cb6fc171d61b87f6920220bc5c9069d31f47d9a9c9e1096e93dfe37863f29eec`.

The upstream [Credits and sources](https://github.com/ahiraz/israel-job-search/blob/7e3a2a8a21c7bea967ddccf6812163ee45adc2f2/README.md#credits-and-sources) credits **[Amir Baldiga / jobsworm](https://github.com/baldiga/jobsworm)** for the board adapters and company list, and **[Michael Lugassy / Techmap](https://github.com/mluggy/techmap)** for the complementary category job lists. Itai is credited for the integrated israel-job-search project, its shared registry, and its reference workflow. Workhunt's separate adaptations and original Job Hunt Kit foundation are documented in the full contribution map.

The bundled upstream materials here are the employer snapshot and MIT notice. Techmap job data is fetched only through a separately configured source and is not bundled in this directory.
