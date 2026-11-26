# Freelance and matching sources

Read the authoritative [28-source catalog](opportunity-sources.json). These are dated reference notes, not active collectors or fresh provider verification. Source selection follows explicit private preferences.

## Freelancer.com (`freelancer`)

https://www.freelancer.com/

Access: Public basic search succeeded without credentials; the official SDK documents OAuth 2.0 for general API access.

Limitations: Anonymous employer identity, reputation and country details were not established.; API reachability does not verify proposal eligibility or current account access.

## Freelancehunt (`freelancehunt`)

https://freelancehunt.com/

Access: Account-generated Bearer token from Apps and API settings.

Limitations: Some Plus-only details are restricted.; No public-project webhook or incremental changed-since filter was confirmed.; Country and payment eligibility were not checked.

## Upwork (`upwork`)

https://www.upwork.com/

Access: Approved application credentials, OAuth 2.0 and the granted marketplace-read scope.

Limitations: Account eligibility and approval are unknown.; No unrestricted global new-project webhook was verified.; RSS support ended after 2024-08-20.

## FL.ru (`fl_ru`)

https://www.fl.ru/projects/

Access: None required in the observed feed requests.

Limitations: Regional optional source; Candidate country account/payment eligibility was not checked.; A functioning RSS feed does not verify every posting or its proposal route.

## Codeur.com (`codeur`)

https://www.codeur.com/projects

Access: None required in the observed feed requests.

Limitations: Live first-party RSS, not a documented REST API contract.; French-language source; do not infer French proficiency from private candidate evidence.; Candidate country account/payment eligibility was not checked.

## PeoplePerHour (`peopleperhour`)

https://www.peopleperhour.com/

Access: Account saved searches; separately authorized mailbox access would be needed for ingestion.

Limitations: No alert was configured and no mailbox was accessed.; Email ingestion would not be a PeoplePerHour project API.

## Workana (`workana`)

https://www.workana.com/

Access: Account project-notification settings; separately authorized mailbox access would be needed for ingestion.

Limitations: No alert was configured and no mailbox was accessed.

## Freelancermap (`freelancermap`)

https://www.freelancermap.com/projects

Access: Account project alerts; Basic one alert and Premium unlimited per current help.

Limitations: Do not configure the unavailable RSS endpoint as an active source.; Advertised XML/JSON interface imports employer projects; it is not confirmed discovery/export.; No alert, subscription or mailbox ingestion was set up.; Remote labels do not establish worldwide eligibility; inspect required language, presence and country restrictions.; The cited listing is activity evidence, not a verified application recommendation.; No public discovery API or global new-project webhook was verified.

## XPlace (`xplace`)

https://www.xplace.com/

Access: Use the established project-search workflow and current account terms.

Limitations: Do not infer an API from listings mentioning API development.; Search access does not authorize paid proposal access.

## Fiverr (`fiverr`)

https://www.fiverr.com/

Access: See catalog access fields.

Limitations: Do not claim Fiverr has no official API/integration.; Do not configure supplier search as new-project discovery.

## Guru (`guru`)

https://www.guru.com/

Access: See catalog access fields.

Limitations: A 403 does not prove that no API exists.; Do not configure an unverified historic RSS/API URL as a working monitor.

## Malt (`malt`)

https://www.malt.com/

Access: Freelancer account and business-identity verification. Israel is listed as an allowed registration country for eligible registered businesses; the user's account and payment setup were not tested.

Limitations: API existence alone does not establish public project discovery.; No public job-post stream or global new-project webhook was verified.; Language, client location and business verification can limit matches.; Use the fee shown in the current quote, including country-specific exceptions.; Profile counts and reviews do not prove current openings or that every client originated on Malt.

## Lemon.io (`lemon_io`)

https://lemon.io/

Access: Developer application and screening; matching depends on acceptance and current client demand.

Limitations: No public project-discovery API, RSS feed or global new-project webhook was verified.; Israel-specific intake, screening acceptance and client requirements remain unverified.; Published examples are activity evidence, not verified application routes.

## Proxify (`proxify`)

https://career.proxify.io/

Access: Developer application and screening before access to matched client engagements.

Limitations: No public project-discovery API, RSS feed or global new-project webhook was verified.; Israel intake and current matching availability remain unverified.; A recruitment page is not a verified client project; check actual Angular work, location and mandatory qualifications for each match.

## YunoJuno (`yunojuno`)

https://www.yunojuno.com/

Access: Approved contractor account required for the personal profile-matched RSS URL; no account-specific URL was obtained.

Limitations: The RSS address is account-specific; no generic endpoint is supplied.; A profile-matched feed does not establish coverage of all opportunities.; Israel-specific account and payment eligibility remain unverified.; No numeric polling allowance or global new-project webhook was verified.

## Toptal (`toptal`)

https://www.toptal.com/

Access: Talent application and screening; project access depends on acceptance and matching.

Limitations: No public project-discovery API, RSS feed or global new-project webhook was verified.; Screening acceptance, Israel-specific access and current .NET/Angular matches remain unverified.; Distinguish Core network participation from TopAccess; do not present the paid subscription as a universal charge for every route.

## Contra (`contra`)

https://contra.com/

Access: Account job-feed and matching-email features. The separate MCP needs account authorization; opportunity-discovery access through MCP was not established.

Limitations: No public machine-readable discovery endpoint, polling allowance or global new-project webhook was verified.; Matching emails do not establish complete coverage.; Verified paid portfolio work does not prove the client originated through Contra.; Israel-specific payout setup remains unverified; consult current transaction, payout and currency-conversion fees.
