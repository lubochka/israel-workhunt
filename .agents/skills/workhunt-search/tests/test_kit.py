"""Offline behavior tests for the adapted job kit; never contact job boards.

Run with: python -B -m unittest discover -s skills/workhunt-search/tests -v
All generated profiles, snapshots, and pages are confined to temporary folders.
"""
import copy
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import scan
import render
import records
import qualification
import packets


def board(provider="greenhouse", tenant="fixture-a", region="us"):
    hosts = {
        "greenhouse": "job-boards.greenhouse.io",
        "ashby": "jobs.ashbyhq.com",
        "lever": "jobs.lever.co",
    }
    url = (f"https://{hosts[provider]}/{tenant}" if provider in hosts
           else f"https://www.comeet.co/jobs/fixture/{tenant}")
    return {"provider": provider, "tenant": tenant, "region": region,
            "company": "Synthetic Fixture Employer", "url": url,
            "key": f"{provider}:{region}:{tenant.lower()}"}


def gh_row(**overrides):
    value = {"id": 123456, "internal_job_id": 7788,
             "title": "Senior .NET Angular Developer",
             "absolute_url": "https://job-boards.greenhouse.io/fixture-a/jobs/123456",
             "location": {"name": "Tel Aviv, Israel"},
             "content": "<p>C# .NET and Angular development.</p>",
             "updated_at": "2026-11-25T08:00:00Z"}
    value.update(overrides)
    return value


def opportunity(**overrides):
    value = scan.normalize(board(), [gh_row()])[0]
    value.update(overrides)
    return value


def read_page(path):
    """Extract the actual JSON used by the rendered page, not a parallel model."""
    source = Path(path).read_text(encoding="utf-8")
    start = source.index("const D=") + len("const D=")
    data, consumed = json.JSONDecoder().raw_decode(source[start:])
    if source[start + consumed] != ";":
        raise AssertionError("Embedded JSON is not terminated as one statement")
    return source, data


def synthetic_profile():
    """Explicit synthetic configuration, never a shared candidate default."""
    return {
        "configured": True, "name": "Synthetic Candidate", "headline": "Fixture evidence only",
        "timezone": "Asia/Jerusalem", "language": "en", "eligible_countries": ["IL", "Israel"],
        "location_pattern": r"Israel|Tel Aviv|Jerusalem", "education": [],
        "degree_policy": {"accepted_qualifications": [], "accept_experience_alternative": True},
        "limited_experience": {"react": 1},
        "tracks": {
            "development": {"label": "Development", "title": r"Developer|Fullstack|מפתח", "stack_all": [r"\.NET|C#", "Angular"]},
            "leadership": {"label": "Leadership", "title": "Lead|Manager", "stack_all": [r"\.NET|C#", "Angular"]},
            "analysis": {"label": "Analysis", "title": "Analyst|מנתח", "stack_all": ["ERP|SQL"]},
            "projects": {"label": "Projects", "title": "Freelance|Contract", "stack_all": [r"\.NET|C#", "Angular"]}},
        "project_employment_pattern": "contract|freelance|temporary",
        "matching_aliases": [{"pattern": "דוט[ -]?נט", "replacement": ".NET"}, {"pattern": "אנגולר", "replacement": "Angular"}],
        "search_brief": {"run_type": "manual", "requested_minimum": 10,
                         "tracks": ["development", "leadership", "analysis", "projects"], "required_stack": ["dotnet", "angular"]},
        "directory_enabled": False, "directory_url": "https://example.invalid/directory.json",
        "employer_registry_enabled": False, "techmap_enabled": False, "extra_boards": {}
    }


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workhunt-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / ".workhunt"
        self.work.mkdir()
        self.profile = synthetic_profile()
        self.profile["directory_enabled"] = False
        self.profile["employer_registry_enabled"] = False
        self.profile["techmap_enabled"] = False
        scan.save(self.work / "profile.json", self.profile)
        self.no_network = patch.object(scan, "get", side_effect=AssertionError("Network forbidden in fixture tests"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def fixture(self, items):
        path = self.work / "fixture-input.json"
        scan.save(path, {"boards": items})
        return scan.scan(self.work, fixtures=path)


class AdapterTests(OfflineCase):
    def test_greenhouse_preserves_full_text_and_distinct_dates(self):
        tail = "MANDATORY TAIL REQUIREMENT: Oracle and TOAD"
        raw = "<p>" + ("Enterprise work. " * 400) + "</p><h2>Requirements</h2><p>" + tail + "</p>"
        row = gh_row(content=raw, first_published="2026-10-01T10:00:00Z",
                     application_deadline="2026-12-01T16:00:00Z")
        job = scan.normalize(board(), [row])[0]
        self.assertGreater(len(job["description"]), 2500)
        self.assertIn(tail, job["description"])
        self.assertEqual(job["first_published_at"], row["first_published"])
        self.assertEqual(job["updated_at"], row["updated_at"])
        self.assertEqual(job["last_published_at"], "")
        self.assertEqual(job["deadline"], row["application_deadline"])
        self.assertEqual(job["source_payload"]["content"], raw)

    def test_double_encoded_html_is_readable_and_prospect_is_not_a_vacancy(self):
        rows = [gh_row(content="&amp;lt;p&amp;gt;C# &amp;amp; Angular&amp;lt;/p&amp;gt;"),
                gh_row(id=9090, internal_job_id=None, title="Join our talent community")]
        jobs = scan.normalize(board(), rows)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["description"], "C# & Angular")

    def test_ashby_last_publication_hybrid_and_unlisted(self):
        item = {"title": "Senior Fullstack", "jobUrl": "https://jobs.ashbyhq.com/fixture-a/123",
                "applyUrl": "https://jobs.ashbyhq.com/fixture-a/123/apply",
                "location": "Tel Aviv", "secondaryLocations": [{"location": "Jerusalem"}],
                "descriptionPlain": ".NET Angular", "isListed": True, "isRemote": True,
                "workplaceType": "Hybrid", "publishedAt": "2026-11-24T10:00:00Z"}
        unlisted = dict(item, jobUrl="https://jobs.ashbyhq.com/fixture-a/hidden", isListed=False)
        jobs = scan.normalize(board("ashby"), [item, unlisted])
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["first_published_at"], "")
        self.assertEqual(job["last_published_at"], item["publishedAt"])
        self.assertEqual(job["work_model_stated"], "Hybrid")
        self.assertEqual(job["apply_url"], item["applyUrl"])
        self.assertIn("Jerusalem", job["location"])

    def test_lever_retains_additional_requirements_and_application_url(self):
        item = {"id": "123456", "text": "Senior Fullstack", "hostedUrl": "https://jobs.lever.co/fixture-a/123456",
                "applyUrl": "https://jobs.lever.co/fixture-a/123456/apply",
                "categories": {"location": "Tel Aviv", "allLocations": ["Tel Aviv", "Jerusalem"]},
                "country": "IL", "descriptionPlain": ".NET Angular",
                "lists": [{"text": "Requirements", "content": "<ul><li>SQL Server</li></ul>"}],
                "additionalPlain": "Bachelor's degree required; no experience alternative.",
                "workplaceType": "hybrid"}
        job = scan.normalize(board("lever"), [item])[0]
        self.assertIn("Requirements: SQL Server", job["description"])
        self.assertIn(item["additionalPlain"], job["description"])
        self.assertIn("Jerusalem", job["location"])
        self.assertEqual(job["apply_url"], item["applyUrl"])
        self.assertEqual(job["first_published_at"], "")
        self.assertEqual(job["updated_at"], "")

    def test_comeet_missing_token_or_details_is_failure_not_empty_success(self):
        b = board("comeet", "59.004", "")
        with patch.object(scan, "get", return_value="<html>Changed public site structure</html>"):
            with self.assertRaises(ValueError):
                scan.fetch(b)
        with self.assertRaises(ValueError):
            scan.normalize(b, [{"uid": "7C.767", "name": "Developer",
                                "url_active_page": "https://www.comeet.co/jobs/fixture/59.004/role/7C.767"}])
        with patch.object(scan, "get", side_effect=["{'token' : 'abc-123'}", "not json"]):
            with self.assertRaises(ValueError):
                scan.fetch(b)

    def test_comeet_valid_empty_and_query_rewrite(self):
        url = "https://www.comeet.co/careers-api/2.0/company/59.004/positions?foo=details&token=fixture-token&details=false"
        b = scan.board_from(url, "Synthetic Fixture Employer")
        calls = []
        def fake_get(value):
            calls.append(value)
            return "[]"
        with patch.object(scan, "get", side_effect=fake_get):
            self.assertEqual(scan.fetch(b), [])
        self.assertEqual(len(calls), 1)
        parts = scan.up.urlsplit(calls[0])
        self.assertTrue(parts.path.endswith("/positions"))
        self.assertEqual(scan.up.parse_qs(parts.query), {"foo": ["details"], "token": ["fixture-token"], "details": ["true"]})

    def test_board_detection_uses_real_host_and_query_parameters(self):
        self.assertIsNone(scan.board_from("https://attacker.invalid/job-boards.greenhouse.io/fixture", "X"))
        self.assertIsNone(scan.board_from("https://jobs.lever.co.evil.invalid/fixture", "X"))
        b = scan.board_from("https://boards.greenhouse.io/embed/job_board?tracking=1&for=fixture-a", "X")
        self.assertEqual(b["tenant"], "fixture-a")
        left = scan.board_from("https://www.comeet.com/jobs/fixture/59.004", "X")
        right = scan.board_from("https://www.comeet.co/jobs/fixture/59.004", "X")
        self.assertEqual(left["key"], right["key"])

    def test_null_directory_source_does_not_stop_later_board_discovery(self):
        payload = {"companies": [
            {"name": "Before null", "sourceUrl": "https://jobs.ashbyhq.com/fixture-before"},
            {"name": "No careers link yet", "sourceUrl": None},
            {"name": "Non-string source", "sourceUrl": {"url": "not a documented source"}},
            {"name": "After null", "sourceUrl": "https://jobs.lever.co/fixture-after"},
        ]}
        profile = copy.deepcopy(self.profile)
        profile["directory_enabled"] = True
        profile["extra_boards"] = {}
        with patch.object(scan, "get", return_value=json.dumps(payload)):
            discovered, failures = scan.collect_boards(profile)
        self.assertEqual({b["tenant"] for b in discovered}, {"fixture-before", "fixture-after"})
        self.assertEqual(failures, [])

    def test_identical_job_ids_in_different_tenants_do_not_collide(self):
        jobs = [scan.normalize(board(tenant="fixture-a"), [gh_row()])[0],
                scan.normalize(board(tenant="fixture-b"), [gh_row()])[0],
                scan.normalize(board(tenant="fixture-a", region="eu"), [gh_row()])[0]]
        self.assertEqual(len({j["id"] for j in jobs}), 3)
        self.assertEqual({j["job_id"] for j in jobs}, {"123456"})


class ClassificationTests(OfflineCase):
    def test_leadership_and_analyst_tracks_survive_default_filtering(self):
        lead = scan.classify(opportunity(title="R&D Manager / Team Lead", description="Hands-on C# .NET Angular"), self.profile)
        analyst = scan.classify(opportunity(title="מנתח/ת מערכות", description="אפיון מערכות ERP ו SQL ואינטגרציות"), self.profile)
        self.assertIn("leadership", lead["tracks"])
        self.assertIn("analysis", analyst["tracks"])
        self.assertEqual(lead["fit_status"], "unreviewed")
        self.assertEqual(analyst["fit_status"], "unreviewed")

    def test_degree_mentions_are_evidence_not_automatic_eligibility(self):
        job = scan.classify(opportunity(description="C# .NET Angular\nBachelor's degree is required.\nFive years' experience."), self.profile)
        self.assertTrue(any("required" in x for x in job["education_excerpts"]))
        self.assertEqual(job["fit_status"], "unreviewed")
        self.assertEqual(job["application_status"], "listing_only")

    def test_structured_us_country_does_not_become_israel_from_illinois_abbreviation(self):
        row = {"id": "us-fixture", "text": "Senior .NET Angular Developer",
               "hostedUrl": "https://jobs.lever.co/fixture-a/us-fixture",
               "categories": {"location": "Springfield, IL"}, "country": "US",
               "descriptionPlain": "C# .NET Angular", "workplaceType": "on-site"}
        job = scan.classify(scan.normalize(board("lever"), [row])[0], self.profile)
        self.assertEqual(job["location_scope"], "needs_location_check")

    def test_bare_illinois_abbreviation_is_unknown_but_structured_israel_is_preserved(self):
        ambiguous = scan.normalize(board(), [gh_row(location={"name": "Springfield, IL"})])[0]
        self.assertEqual(scan.classify(ambiguous, self.profile)["location_scope"], "needs_location_check")
        israel = {"id": "israel-fixture", "text": "Senior .NET Angular Developer",
                  "hostedUrl": "https://jobs.lever.co/fixture-a/israel-fixture",
                  "categories": {"location": "Remote"}, "country": "IL",
                  "descriptionPlain": "C# .NET Angular"}
        explicit = scan.normalize(board("lever"), [israel])[0]
        self.assertEqual(scan.classify(explicit, self.profile)["location_scope"], "configured_geography")

    def test_contract_employment_type_routes_generic_developer_to_projects(self):
        row = {"title": "Software Developer", "jobUrl": "https://jobs.ashbyhq.com/fixture-a/contract-role",
               "descriptionPlain": "Build .NET Angular systems.", "location": "Tel Aviv",
               "employmentType": "Contract", "isListed": True}
        job = scan.classify(scan.normalize(board("ashby"), [row])[0], self.profile)
        self.assertIn("projects", job["tracks"])
        self.assertIn("development", job["tracks"])
        self.assertEqual(job["fit_status"], "unreviewed")


class SnapshotTests(OfflineCase):
    def test_search_requires_an_explicit_execution_mode(self):
        with self.assertRaises(ValueError):
            scan.scan(self.work)
        self.assertFalse(list(self.work.glob("runs/*/meta.json")))

    def test_runs_are_unique_and_previous_evidence_unchanged(self):
        item = {"board": board(), "jobs": [gh_row()]}
        first = self.fixture([item])
        evidence = {p.name: p.read_bytes() for p in first.iterdir() if p.is_file()}
        second = self.fixture([{"board": board(), "jobs": [gh_row(content="Updated .NET Angular details")]}])
        self.assertNotEqual(first, second)
        self.assertEqual(evidence, {p.name: p.read_bytes() for p in first.iterdir() if p.is_file()})
        old_job = scan.load(first / "hits.json")[0]
        new_job = scan.load(second / "hits.json")[0]
        self.assertTrue(old_job["new_to_tracker"])
        self.assertFalse(new_job["new_to_tracker"])
        self.assertEqual(new_job["first_seen_at"], old_job["first_seen_at"])

    def test_failed_board_and_successful_absence_have_distinct_nonclosure_states(self):
        self.fixture([{"board": board(), "jobs": [gh_row()]}])
        failed = self.fixture([{"board": board(), "error": "synthetic timeout"}])
        changes = scan.load(failed / "changes.json")
        self.assertEqual([x["status"] for x in changes], ["not_checked"])
        back = self.fixture([{"board": board(), "jobs": [gh_row()]}])
        self.assertFalse(scan.load(back / "hits.json")[0]["new_to_tracker"])
        empty = self.fixture([{"board": board(), "jobs": []}])
        self.assertEqual([x["status"] for x in scan.load(empty / "changes.json")], ["not_listed_in_successful_scan"])

    def test_fixtures_do_not_read_or_overwrite_live_records(self):
        synthetic_job = opportunity()
        # Exercise the live branch with an entirely mocked transport, in the temp folder.
        with patch.object(scan, "collect_boards", return_value=([board()], [])), patch.object(scan, "fetch", return_value=[synthetic_job]):
            live_run = scan.scan(self.work, network=True)
        scan.save(self.work / "reviews.json", {synthetic_job["id"]: {"fit": "exclude", "reason": "live-only review"}})
        scan.save(self.work / "applications.json", {synthetic_job["id"]: {"status": "user_reported_submitted"}})
        (self.work / "jobs.html").write_text("LIVE OUTPUT SENTINEL", encoding="utf-8")
        fixture_run = self.fixture([{"board": board(), "jobs": [gh_row()]}])
        self.assertTrue(scan.load(fixture_run / "hits.json")[0]["new_to_tracker"])
        fixture_page = render.render(self.work, fixture_run, fixture=True)
        _, data = read_page(fixture_page)
        self.assertTrue(data["fixture_mode"])
        self.assertEqual(data["jobs"][0]["review"]["fit"], "unreviewed")
        self.assertEqual(data["jobs"][0]["application_state"], "not_recorded")
        self.assertEqual((self.work / "jobs.html").read_text(encoding="utf-8"), "LIVE OUTPUT SENTINEL")
        with self.assertRaises(ValueError):
            render.render(self.work, fixture_run, fixture=False)
        with self.assertRaises(ValueError):
            render.render(self.work, live_run, fixture=True)


class ReviewTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.now = dt.datetime(2026, 11, 25, 12, 0, tzinfo=dt.timezone.utc)
        self.job = opportunity()
        self.good = {
            "fit": "strong", "reason": "Synthetic example: documented .NET and Angular evidence.",
            "route": {"status": "form_observed", "checked_at": "2026-11-25T11:00:00Z",
                      "job_identifier": "123456", "source_url": self.job["url"],
                      "evidence": "Fixture form heading contains requisition 123456."},
            "publication": {"kind": "first_published", "at": "2026-11-25T08:00:00Z", "source_url": self.job["url"],
                            "evidence": "Fixture original publication field."},
            "degree_status": "not_stated", "degree_evidence": "Fixture full requirements contain no education clause.",
            "requirements": [{"requirement": ".NET and Angular", "mandatory": True, "met": True,
                              "evidence": "Synthetic CV paragraph, used only by offline tests."}],
            "cv_file": "synthetic-cv.pdf",
            "constraints_clear": True, "duplicate_checked": True, "full_description_read": True,
            "role": {"track": "development", "confirmed": True, "evidence": "Senior developer role"},
            "stack": {"dotnet": True, "angular": True, "evidence": "Both substantive in duties"},
            "geography": {"eligible": True, "eligible_from": ["IL"], "evidence": "Tel Aviv Israel"},
        }

    def evaluate(self, review):
        return render.effective_review(self.job, review, self.profile, self.now, {"opportunities": []}, {"records": []})

    def test_complete_review_remains_strong(self):
        value = self.evaluate(self.good)
        self.assertEqual(value["fit"], "strong")
        self.assertEqual(value["verification_gaps"], [])

    def test_material_missing_or_stale_evidence_downgrades_recommendation(self):
        changes = [
            ("stale route", lambda r: r["route"].update(checked_at="2026-11-20T11:00:00Z")),
            ("future route", lambda r: r["route"].update(checked_at="2026-11-26T11:00:00Z")),
            ("login barrier", lambda r: r["route"].update(status="login_required")),
            ("unsupported repost claim", lambda r: r["publication"].update(kind="last_published")),
            ("future publication", lambda r: r["publication"].update(at="2026-11-26T12:00:00Z")),
            ("unproven mandatory skill", lambda r: r["requirements"][0].update(met=False)),
            ("no degree evidence", lambda r: r.update(degree_evidence="")),
            ("no duplicate check", lambda r: r.update(duplicate_checked=False)),
            ("no CV choice", lambda r: r.update(cv_file="")),
        ]
        for title, mutate in changes:
            with self.subTest(title):
                review = copy.deepcopy(self.good)
                mutate(review)
                result = self.evaluate(review)
                self.assertEqual(result["fit"], "clarify")
                self.assertTrue(result["verification_gaps"])

    def test_hard_degree_conflict_and_expired_deadline_exclude(self):
        review = copy.deepcopy(self.good)
        review["degree_status"] = "mandatory_no_alternative"
        self.assertEqual(self.evaluate(review)["fit"], "exclude")
        self.job["deadline"] = "2026-11-24T15:00:00Z"
        self.assertEqual(self.evaluate(self.good)["fit"], "exclude")

    def test_wrong_requisition_form_cannot_verify_a_different_job(self):
        review = copy.deepcopy(self.good)
        review["route"].update(job_identifier="999999", source_url="https://job-boards.greenhouse.io/fixture-a/jobs/999999",
                               evidence="Fixture form clearly identifies a different requisition 999999.")
        self.assertNotEqual(self.evaluate(review)["fit"], "strong")

    def test_explicitly_closed_route_is_excluded(self):
        review = copy.deepcopy(self.good)
        review["route"].update(status="closed", evidence="Exact fixture requisition says no longer accepting applications.")
        self.assertEqual(self.evaluate(review)["fit"], "exclude")

    def test_application_states_require_timestamp_and_evidence(self):
        for status in ("submitted_observed", "receipt_observed", "response_received"):
            with self.subTest(status):
                self.assertEqual(render.application_state({"status": status}), "unverified_submission_claim")
                self.assertEqual(render.application_state({"status": status, "evidence": "fixture receipt", "at": "2026-11-24"}), "unverified_submission_claim")
                self.assertEqual(render.application_state({"status": status, "evidence": "fixture receipt", "at": "2026-11-24T10:00:00Z"}), status)
        self.assertEqual(render.application_state({"status": "user_reported_submitted"}), "user_reported_submitted")
        self.assertEqual(render.application_state({"status": "historical_claim_only"}), "historical_claim_only")
        self.assertEqual(render.application_state({"status": "sent"}), "unknown")

    def test_future_submission_timestamp_cannot_be_observed_now(self):
        value = {"status": "submitted_observed", "evidence": "future fixture receipt", "at": "2099-01-01T10:00:00Z"}
        self.assertEqual(render.application_state(value), "unverified_submission_claim")


class PageTests(OfflineCase):
    def test_empty_workspace_renders_without_inventing_matches(self):
        _, data = read_page(render.render(self.work))
        self.assertEqual(data["jobs"], [])
        self.assertEqual(data["meta"], {})
        self.assertFalse(data["fixture_mode"])

    def test_data_cannot_break_out_of_script_and_survives_round_trip(self):
        evil = '</script><img src=x onerror="globalThis.compromised=true"><script>throw Error("injected")</script>'
        self.profile["name"] = evil
        self.profile["headline"] = "Text with < > & and Hebrew שלום"
        scan.save(self.work / "profile.json", self.profile)
        item = {"id": "manual:fixture:xss", "company": evil, "title": evil,
                "url": "https://example.invalid/fixture", "description": evil}
        scan.save(self.work / "manual-opportunities.json", [item])
        scan.save(self.work / "reviews.json", {item["id"]: {"fit": "clarify", "reason": evil}})
        source, data = read_page(render.render(self.work))
        self.assertEqual(data["name"], evil)
        self.assertEqual(data["jobs"][0]["description"], evil)
        self.assertEqual(data["jobs"][0]["review"]["reason"], evil)
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []
            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
        parsed = Tags()
        parsed.feed(source)
        self.assertEqual(parsed.tags.count("script"), 1)
        self.assertNotIn("img", parsed.tags)

    def test_nonweb_or_credential_urls_cannot_enter_manual_links(self):
        for bad in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "https://user:password@example.invalid/fixture"):
            with self.subTest(bad):
                scan.save(self.work / "manual-opportunities.json", [{"id": "manual:fixture:url", "company": "Fixture", "title": "Role", "url": bad, "description": "Synthetic"}])
                with self.assertRaises(ValueError):
                    render.render(self.work)


class CurrentPolicyTests(ReviewTests):
    def test_exact_75_percent_and_duplicate_criteria(self):
        review = copy.deepcopy(self.good)
        review["requirements"] = [{"requirement": name, "met": met, "evidence": "CV evidence" if met else "Unverified"}
                                  for name, met in [("C#", True), ("Angular", True), ("SQL", True), ("Oracle", False)]]
        review["requirements"].append(dict(review["requirements"][0]))
        result = self.evaluate(review)
        self.assertEqual((result["score"]["supported"], result["score"]["total"]), (3, 4))
        self.assertEqual(result["fit"], "strong")
        self.assertEqual(result["score"]["gaps"], ["Oracle"])
        review["requirements"][1]["evidence"] = ""
        self.assertEqual(self.evaluate(review)["fit"], "clarify")

    def test_long_limited_technology_requirement_is_hard_exclusion_with_alternative(self):
        review = copy.deepcopy(self.good)
        review["requirements"] = [{"requirement": k, "met": True, "evidence": "CV"} for k in ["C#", "SQL", "Angular"]]
        review["requirements"].append({"requirement": "2 years React", "technology": "react", "minimum_years": 2, "met": False})
        self.assertEqual(self.evaluate(review)["fit"], "exclude")
        review["requirements"][-1].update(alternative_met=True, alternative_evidence="Angular explicitly accepted instead")
        self.assertEqual(self.evaluate(review)["fit"], "strong")

    def test_genuine_refresh_and_qualified_login_are_accepted(self):
        review = copy.deepcopy(self.good)
        review["publication"].update(kind="refresh", genuine_publication_event=True)
        review["route"].update(status="login_required", exact_vacancy_accepting_applications=True)
        result = self.evaluate(review)
        self.assertEqual(result["fit"], "strong")
        self.assertEqual(result["route"]["label"], qualification.LOGIN_LABEL)
        review["publication"]["kind"] = "source_updated"
        self.assertFalse(self.evaluate(review)["qualified"])

    def test_email_api_url_partial_description_and_wrong_employer_do_not_qualify(self):
        for change in [lambda r: r["route"].update(status="email_advertised"),
                       lambda r: r.update(full_description_read=False),
                       lambda r: r["route"].update(job_identifier=self.job["title"], source_url="https://other.invalid/jobs/123456")]:
            review = copy.deepcopy(self.good)
            change(review)
            self.assertFalse(self.evaluate(review)["qualified"])

    def test_date_only_and_outside_window_do_not_invent_precision(self):
        review = copy.deepcopy(self.good)
        review["publication"].pop("at")
        review["publication"].update(date="2026-11-25", timezone="Asia/Jerusalem")
        self.assertFalse(self.evaluate(review)["qualified"])

    def test_broader_track_and_unknown_remote_geography_fail_separate_gates(self):
        review = copy.deepcopy(self.good)
        review["role"]["track"] = "delivery"
        review["geography"] = {"evidence": "Remote"}
        result = self.evaluate(review)
        self.assertTrue(result["score"]["passes"])
        self.assertFalse(result["checks"]["role"])
        self.assertFalse(result["checks"]["geography"])

    def test_history_must_actually_be_available(self):
        found, applied = records.read_store(self.work)
        result = render.effective_review(self.job, self.good, self.profile, self.now, found, applied)
        self.assertFalse(result["checks"]["history"])

    def test_brief_minimum_is_not_cap_and_notifications_have_no_invented_five(self):
        brief = qualification.search_brief(self.profile, self.now)
        self.assertEqual(brief["requested_minimum"], 10)
        self.assertIsNone(brief["result_cap"])
        self.assertEqual(records.timestamp(brief["window_end"]) - records.timestamp(brief["window_start"]), dt.timedelta(hours=24))
        notification = qualification.search_brief(self.profile, self.now, {"run_type": "notification"})
        self.assertIsNone(notification["requested_minimum"])
        self.assertTrue(notification["silence_if_zero"])

    def test_rolling_window_is_24_elapsed_hours_across_israel_dst(self):
        from zoneinfo import ZoneInfo
        end = dt.datetime(2026, 10, 25, 12, tzinfo=ZoneInfo("Asia/Jerusalem"))
        brief = qualification.search_brief(self.profile, end)
        start = records.timestamp(brief["window_start"])
        self.assertEqual(end.timestamp() - start.timestamp(), 24 * 3600)
        self.assertEqual(start.hour, 13)


class CanonicalHistoryTests(OfflineCase):
    def test_employer_alias_requires_exact_requisition_and_refresh_does_not_escape(self):
        a = {"records": [{"id": "one", "company": "Employer A", "source_job_id": "11", "identity_aliases": ["Supplier A"], "suppress_from_new_results": True}]}
        f = {"opportunities": []}
        self.assertEqual(records.history_decision({"id": "new-url", "company": "Supplier A", "job_id": "11"}, f, a)["state"], "suppressed")
        for other in [{"company": "Supplier A", "job_id": "12"}, {"company": "Employer B", "job_id": "11"}]:
            self.assertEqual(records.history_decision(other, f, a)["state"], "new")

    def test_url_aliases_cross_sources_but_functional_query_ids_stay_distinct(self):
        row = {"id": "canonical", "source_url": "https://example.invalid/jobs?id=11", "source_aliases": ["https://mirror.invalid/role/abc"], "history": {"reported_in_chat": True}}
        f = {"opportunities": [row]}
        self.assertEqual(records.history_decision({"url": "https://mirror.invalid/role/abc?utm_source=feed"}, f, {"records": []})["state"], "previously_reported")
        self.assertEqual(records.history_decision({"url": "https://example.invalid/jobs?id=12"}, f, {"records": []})["state"], "new")

    def test_private_suppression_is_scoped_without_global_defaults(self):
        applied = {"records": [{"id": "synthetic-suppressed", "company": "Synthetic Supplier", "job_id": "fixture-42", "suppress_from_new_results": True}]}
        self.assertEqual(records.history_decision({"company": "Synthetic Supplier", "job_id": "fixture-42"}, {}, applied)["state"], "suppressed")
        self.assertEqual(records.history_decision({"company": "Synthetic Supplier", "job_id": "fixture-other"}, {}, applied)["state"], "new")
        self.assertEqual(records.history_decision({"company": "Synthetic Supplier", "job_id": "fixture-42"}, {}, {})["state"], "new")

    def test_prepared_uploaded_reported_and_submitted_are_independent(self):
        for status, expected in [("prepared", "new"), ("uploaded", "new"), ("user_reported_applied", "already_applied"), ("submitted_observed", "already_applied")]:
            row = {"id": "x", "submission_status": status, "evidence": "Evidence", "submitted_at": "2026-01-01T10:00:00Z"}
            self.assertEqual(records.history_decision({"id": "x"}, {}, {"records": [row]})["state"], expected)
        self.assertEqual(records.application_state({"submission_status": "platform_verified_historical_application", "evidence": ["Observed prior history"]}), "platform_verified_historical_application")

    def test_canonical_renderer_uses_history_and_leaves_all_records_byte_identical(self):
        job = opportunity()
        canonical = {"schema_version": 1, "opportunities": [job], "search_runs": []}
        applied = {"records": [{"id": job["id"], "submission_status": "user_reported_applied", "suppress_from_new_results": True}]}
        scan.save(self.work / "data/jobs.json", canonical) if (self.work / "data").exists() else None
        records.save(self.work / "data/jobs.json", canonical)
        records.save(self.work / "data/applied_jobs.json", applied)
        before = {p.name: p.read_bytes() for p in (self.work / "data").iterdir()}
        _, data = read_page(render.render(self.work))
        self.assertEqual(data["jobs"][0]["application_state"], "user_reported_submitted")
        self.assertEqual(data["jobs"][0]["review"]["decision"], "suppressed")
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.work / "data").iterdir()})

    def test_merge_preserves_personal_assessment_and_source_provenance(self):
        old = {"id": "canonical", "source_url": "https://example.invalid/11", "submission": {"status": "user_reported_submitted"}, "reported_at": "old", "first_seen_at": "first", "custom": {"keep": True}}
        source = {"id": "scanner:11", "url": old["source_url"], "description": "Full fresh text"}
        result = records.merge_discovery({"opportunities": [old], "search_runs": []}, [source], {"checked_at": "now"})
        self.assertEqual(len(result["opportunities"]), 1)
        for key in old:
            self.assertEqual(result["opportunities"][0][key], old[key])
        self.assertEqual(result["opportunities"][0]["observations"], [source])


class PacketTests(OfflineCase):
    def test_manifest_current_english_and_preparation_never_changes_submission(self):
        import hashlib
        cv = self.work / "synthetic-cv.pdf"
        cv.write_bytes(b"synthetic PDF bytes")
        records.save(self.work / "cv-manifest.json", {"versions": [{"version_id": "test-current", "language": "en", "roles": ["development"], "path": cv.name, "selection_status": "current", "sha256": hashlib.sha256(cv.read_bytes()).hexdigest()}]})
        job = opportunity()
        prior = {"status": "user_reported_submitted"}
        records.save(self.work / "data/jobs.json", {"opportunities": [{**job, "submission": prior}], "search_runs": []})
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        now = dt.datetime.now(dt.timezone.utc)
        packet = packets.prepare_packet(self.work, job, {}, qualification.search_brief(self.profile, now), now, "en", "development", drafts=[{"text": "Local draft", "language": "en"}], observed_questions=[{"question": "Start date?"}])
        self.assertEqual(packet["cv"]["file_status"], "hash_matches")
        self.assertEqual(packet["submission_state"], "not_sent")
        self.assertEqual(packet["drafts"][0]["state"], "not_sent")
        self.assertEqual(len(packet["form"]["unresolved_answers"]), 1)
        packets.save_packet(self.work, packet)
        row = records.load(self.work / "data/jobs.json")["opportunities"][0]
        self.assertEqual(row["submission"], prior)
        self.assertFalse((self.work / "applications.json").exists())
        cv.write_bytes(b"changed")
        self.assertEqual(packets.select_cv(self.work, "en", "development")["file_status"], "changed_since_manifest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
