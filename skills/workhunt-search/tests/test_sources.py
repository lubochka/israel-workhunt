"""Synthetic source/registry tests; never call live employers or CSV feeds."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import adapters
import records
import scan
import source_registry as registry
from test_kit import OfflineCase, board, gh_row, opportunity


def smart_board():
    return registry.board_from("https://careers.smartrecruiters.com/Fixture", "Fixture Employer")


def smart_detail(ident, **kwargs):
    row = {"id": str(ident), "uuid": "uuid-" + str(ident), "name": "Senior C# .NET Angular Developer", "refNumber": "REF-" + str(ident),
           "jobId": "job-" + str(ident), "jobAdId": "ad-" + str(ident), "active": True,
           "postingUrl": "https://jobs.smartrecruiters.com/Fixture/" + str(ident), "applyUrl": "https://jobs.smartrecruiters.com/Fixture/" + str(ident) + "/apply",
           "location": {"city": "London", "country": "GB"}, "secondaryLocations": [{"city": "Tel Aviv", "country": "IL"}],
           "releasedDate": "2026-11-26T12:00:00Z", "jobAd": {"sections": {"companyDescription": {"title": "Company", "text": "Fixture"},
             "jobDescription": {"title": "Work", "text": "<p>.NET Angular</p>"}, "qualifications": {"title": "Requirements", "text": "<p>SQL</p>"},
             "additionalInformation": {"title": "Additional", "text": "<p>Tail mandatory information</p>"}}}}
    row.update(kwargs)
    return row


class SmartRecruitersTests(OfflineCase):
    def test_paginates_over_400_and_preserves_long_full_detail(self):
        requests = []
        def transport(url):
            requests.append(url)
            query = scan.up.parse_qs(scan.up.urlsplit(url).query)
            if query:
                offset = int(query["offset"][0]);limit = int(query["limit"][0])
                return json.dumps({"offset": offset, "limit": limit, "totalFound": 451,
                                   "content": [{"id": str(i), "name": "Developer"} for i in range(offset, min(451, offset + limit))]})
            row = smart_detail(url.rsplit("/", 1)[1])
            row["jobAd"]["sections"]["additionalInformation"]["text"] = "<p>" + "Evidence " * 1100 + "MANDATORY END</p>"
            return json.dumps(row)
        with patch.object(scan, "get", side_effect=transport):
            result = scan.fetch(smart_board())
        self.assertEqual(len(result), 451)
        self.assertEqual(result.errors, [])
        self.assertEqual(len([u for u in requests if "?" in u]), 5)
        self.assertGreater(len(result[0]["description"]), 8000)
        self.assertIn("MANDATORY END", result[0]["description"])
        self.assertIn("Tel Aviv", result[0]["location"])
        self.assertEqual(result[0]["provider_identifiers"]["refNumber"], "REF-0")
        self.assertEqual(result[0]["first_published_at"], "")
        self.assertEqual(scan.classify(result[0], self.profile)["location_scope"], "configured_geography")

    def test_failed_detail_retains_identity_and_marks_board_partial(self):
        def transport(url):
            if "?" in url:
                return json.dumps({"totalFound": 2, "offset": 0, "content": [{"id": "1", "name": "First"}, {"id": "2", "name": "Second"}]})
            if url.endswith("/2"):
                raise TimeoutError("fixture")
            return json.dumps(smart_detail("1", active=False))
        with patch.object(scan, "get", side_effect=transport):
            result = scan.fetch(smart_board())
        self.assertFalse(result[0]["active"])
        self.assertFalse(result[1]["description_complete"])
        self.assertEqual(result[1]["job_id"], "2")
        self.assertEqual(result.errors[0]["job_id"], "2")
        with patch.object(scan, "collect_boards", return_value=([smart_board()], [])), patch.object(scan, "fetch", return_value=result):
            run = scan.scan(self.work, network=True)
        meta = scan.load(run / "meta.json")
        self.assertEqual(meta["successful_board_keys"], [])
        self.assertEqual(meta["source_checks"][0]["status"], "partial")
        self.assertTrue(scan.load(run / "all_jobs.json")[0]["qualification"]["hard_exclusions"])

    def test_nonprogress_and_empty_before_total_are_failures(self):
        for rows in [[{"id": "1", "name": "First"}], []]:
            def transport(url):
                if "?" in url:
                    offset = int(scan.up.parse_qs(scan.up.urlsplit(url).query)["offset"][0])
                    return json.dumps({"totalFound": 2, "offset": offset, "content": rows})
                return json.dumps(smart_detail("1"))
            with patch.object(scan, "get", side_effect=transport):
                result = scan.fetch(smart_board())
            self.assertTrue(result.errors)

    def test_successful_zero_is_not_failure(self):
        with patch.object(scan, "get", return_value=json.dumps({"totalFound": 0, "offset": 0, "content": []})):
            result = scan.fetch(smart_board())
        self.assertEqual(result, [])
        self.assertEqual(result.errors, [])


class TechmapTests(OfflineCase):
    def csv(self, rows):
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["company", "category", "size", "title", "level", "city", "url", "updated"])
        writer.writeheader();writer.writerows(rows)
        return "\ufeff" + output.getvalue()

    def test_all_categories_integrated_without_geo_date_or_description_inference(self):
        profile = {**self.profile, "techmap_enabled": True}
        boards, failed = scan.collect_boards(profile, self.work)
        self.assertEqual(len(boards), 19)
        self.assertEqual(failed, [])
        row = {"company": "Synthetic", "title": "מפתח C# דוט נט ואנגולר", "city": "תל אביב", "url": "https://example.invalid/jobs?req=11", "updated": "2026-11-26"}
        job = adapters.techmap_parse(boards[0], self.csv([row]))[0]
        self.assertIn("C#", job["title"])
        self.assertIn("development", scan.classify(job, profile)["tracks"])
        self.assertEqual(scan.classify(job, profile)["location_scope"], "needs_location_check")
        self.assertEqual(job["first_published_at"], "")
        self.assertEqual(job["source_updated_at"], row["updated"])
        self.assertEqual(job["source_updated_precision"], "date")
        self.assertFalse(job["description_complete"])
        self.assertEqual(job["description"], "")
        self.assertEqual(job["provenance"]["license"], "ODbL-1.0")

    def test_same_title_distinct_functional_id_stays_distinct_cross_category_merges(self):
        b = {"key": "techmap::software", "category": "software", "url": "https://example.invalid/software.csv"}
        row = {"company": "Same", "title": "C# .NET Angular Developer", "city": "Tel Aviv", "url": "https://example.invalid/job?req=11", "updated": "2026-11-26"}
        jobs = adapters.techmap_parse(b, self.csv([row, {**row, "url": "https://example.invalid/job?req=12"}]))
        more = adapters.techmap_parse({**b, "key": "techmap::frontend", "category": "frontend"}, self.csv([{**row, "url": row["url"] + "&utm_source=feed"}]))
        merged = adapters.deduplicate_discoveries(jobs + more)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["discovery_categories"], ["software", "frontend"])
        history = {"opportunities": [{"id": "canonical-11", "source_url": row["url"], "history": {"reported_in_chat": True}}]}
        self.assertEqual(records.history_decision(merged[0], history, {"records": []})["state"], "previously_reported")
        self.assertEqual(records.history_decision(merged[1], history, {"records": []})["state"], "new")

    def test_malformed_csv_fails_explicitly(self):
        with self.assertRaises(ValueError):
            adapters.techmap_parse({"key": "techmap::x", "category": "x", "url": "https://example.invalid/feed"}, "title,url\nNo full schema,https://example.invalid")


class RegistryTests(OfflineCase):
    def row(self, **extra):
        return {"name": "Fixture", "provider": "smartrecruiters", "token": "Fixture", "domain": "example.invalid", "careers_url": "https://careers.smartrecruiters.com/Fixture", **extra}

    def test_supported_urls_and_host_boundaries(self):
        for url in ["https://careers.smartrecruiters.com/Fixture", "https://jobs.smartrecruiters.com/Fixture/11", "https://fixture.recruitee.com/o/role"]:
            self.assertIsNotNone(registry.board_from(url, "X"))
        for url in ["https://evil.invalid/jobs.smartrecruiters.com/Fixture", "https://fixture.recruitee.com.evil.invalid", "https://user:pass@jobs.smartrecruiters.com/Fixture"]:
            self.assertIsNone(registry.board_from(url, "X"))

    def test_import_dry_run_check_and_local_corrections_survive_refresh(self):
        snapshot = self.work / "snapshot.json"
        records.save(snapshot, [self.row()])
        result = registry.update_registry(self.work, snapshot)
        self.assertTrue(result["changed"])
        self.assertFalse((self.work / "sources/employer-boards.json").exists())
        registry.update_registry(self.work, snapshot, apply=True)
        override = {"boards": {"smartrecruiters::fixture": {"company": "Local corrected name", "priority": 1}}, "additions": []}
        path = self.work / "sources/employer-overrides.json"
        records.save(path, override);before = path.read_bytes()
        records.save(snapshot, [self.row(name="Upstream changed name")])
        registry.update_registry(self.work, snapshot, apply=True)
        current = records.load(self.work / "sources/employer-boards.json")
        effective = registry.effective_boards(current, records.load(path))
        self.assertEqual(effective[0]["company"], "Local corrected name")
        self.assertEqual(effective[0]["priority"], 1)
        self.assertEqual(effective[0]["health"]["status"], "unverified")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(registry.update_registry(self.work, snapshot)["changed"])

    def test_removed_upstream_is_not_deleted_or_claimed_closed(self):
        old = registry.build_registry([self.row()])
        new = registry.build_registry([], old)
        self.assertEqual(len(new["boards"]), 1)
        self.assertEqual(new["boards"][0]["upstream_presence"], "missing_in_latest_snapshot")
        self.assertEqual(new["boards"][0]["health"]["status"], "unverified")

    def test_live_collection_uses_registry_overrides_priority(self):
        records.save(self.work / "sources/employer-boards.json", registry.build_registry([self.row()]))
        records.save(self.work / "sources/employer-overrides.json", {"boards": {"smartrecruiters::fixture": {"priority": 0}}})
        sources, failed = scan.collect_boards({**self.profile, "employer_registry_enabled": True}, self.work)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["priority"], 0)
        self.assertEqual(failed, [])

    def test_health_keeps_last_success_across_failure_and_not_checked(self):
        checks = [{"board_key": "smartrecruiters::fixture", "status": "successful_empty", "records": 0}]
        registry.record_source_checks(self.work, self.profile, checks, "2026-11-26T10:00:00Z")
        registry.record_source_checks(self.work, self.profile, [{"board_key": checks[0]["board_key"], "status": "fetch_failed", "records": None}], "2026-11-26T11:00:00Z")
        registry.record_source_checks(self.work, self.profile, [{"board_key": checks[0]["board_key"], "status": "not_checked"}], "2026-11-26T12:00:00Z")
        value = records.load(self.work / "sources/source-health.json")["sources"][checks[0]["board_key"]]
        self.assertEqual(value["last_successful_record_count"], 0)
        self.assertEqual(value["last_successful_check_at"], "2026-11-26T10:00:00Z")
        self.assertEqual(value["last_attempt_at"], "2026-11-26T11:00:00Z")
        self.assertEqual(value["status"], "not_checked")


class RecruiteeTests(OfflineCase):
    XML = '''<jobs><job><reference>123</reference><title>Senior .NET Angular Developer</title><company>Fixture</company>
    <description_requirements><![CDATA[<p>Full description and requirements .NET Angular SQL</p>]]></description_requirements>
    <city>London</city><country>GB</country><locations><location><city>London</city><country>GB</country></location><location><city>Tel Aviv</city><country>IL</country></location></locations>
    <url>https://fixture.recruitee.com/o/123</url><apply_url>https://fixture.recruitee.com/o/123/c/new</apply_url>
    <posted>2026-11-26T10:00:00Z</posted><updated>2026-11-26T12:00:00Z</updated><hybrid>true</hybrid></job></jobs>'''

    def test_conditional_xml_preserves_all_locations_and_distinct_feed_dates(self):
        b = registry.board_from("https://fixture.recruitee.com", "Fixture")
        with patch.object(scan, "get", return_value=self.XML) as get:
            jobs = scan.fetch(b)
        self.assertTrue(get.call_args.args[0].endswith("/api/feeds/offers.xml"))
        self.assertEqual(len(jobs[0]["locations"]), 2)
        self.assertIn("Tel Aviv", jobs[0]["location"])
        self.assertEqual(jobs[0]["first_published_at"], "")
        self.assertEqual(jobs[0]["feed_added_at"], "2026-11-26T10:00:00Z")
        self.assertEqual(jobs[0]["source_updated_at"], "2026-11-26T12:00:00Z")
        self.assertEqual(jobs[0]["json_auth_transition_at"], "2027-02-10")
        self.assertEqual(jobs[0]["application_status"], "listing_only")

    def test_login_html_missing_description_or_entity_is_failure_not_zero(self):
        b = registry.board_from("https://fixture.recruitee.com", "Fixture")
        for bad in ["<html>Login</html>", self.XML.replace("description_requirements", "unrecognized"), '<!DOCTYPE jobs [<!ENTITY x "test">]><jobs/>']:
            with patch.object(scan, "get", return_value=bad):
                with self.assertRaises(ValueError):
                    scan.fetch(b)

    def test_first_city_only_keeps_secondary_unknown(self):
        b = registry.board_from("https://fixture.recruitee.com", "Fixture")
        import re
        rows = adapters.recruitee_parse(b, re.sub(r"<locations>.*?</locations>", "", self.XML), scan.plain)
        self.assertEqual(rows[0]["secondary_locations_status"], "unknown")
        self.assertEqual(len(rows[0]["locations"]), 1)


if __name__ == "__main__":
    unittest.main()
