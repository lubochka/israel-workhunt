# Remote job and contract sources

Read the authoritative [23-source catalog](opportunity-sources.json). These are dated reference notes, not active collectors or fresh provider verification. Source selection follows explicit private preferences.

## Himalayas (`himalayas`)

https://himalayas.app/

Access: Public access without a key; optional free Bearer key for a separate account allowance.

Limitations: Check employmentType, locationRestrictions and timezoneRestrictions.; Use applicationLink and visible Himalayas source credit; preserve applicable API terms.

## Remote OK (`remote_ok`)

https://remoteok.com/

Access: No authentication required by the official public-feed guidance.

Limitations: Skip legal/metadata objects rather than treating every array element as a job.; Filter contract type, stack and location locally; retain original job links and credit.

## We Work Remotely (`we_work_remotely`)

https://weworkremotely.com/

Access: Public RSS; no authentication required in the observed request.

Limitations: RSS is the verified discovery interface; the separate partner posting API is not a search API.; Keep source attribution and links; deduplicate overlapping category feeds.

## Jobicy (`jobicy`)

https://jobicy.com/

Access: No key required for public listing URLs; paid/direct-ATS-link access is a separate optional service.

Limitations: Absence from the seven-day feed does not establish closure.; Credit Jobicy and preserve its listing links for public API data.; Discover current industry/location slugs rather than inventing them.

## Remotive (`remotive`)

https://remotive.com/

Access: Public API; no credentials used in the successful parent requests.

Limitations: Validate filters and coverage; match locally, and do not claim the observed 15 rows are a documented permanent cap.; Credit and link back to Remotive; redistribution and signup-gated listing restrictions apply.

## Braintrust (`braintrust`)

https://www.usebraintrust.com/

Access: Account saved-search settings; separately authorized mailbox access would be needed for ingestion.

Limitations: No public project-discovery API, RSS feed or global new-project webhook was verified.; Filter each opportunity for contract type, actual .NET and Angular work, country, hours and mandatory qualifications.; Payment-country support does not override client location restrictions.
