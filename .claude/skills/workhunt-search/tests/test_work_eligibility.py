"""Configured country/work-path gate; synthetic evidence and no external actions."""
import copy
import datetime as dt
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from test_kit import OfflineCase, eligibility_review, location_policy, opportunity, read_page
import packets
import qualification
import records
import render
import scan
import work_eligibility


class WorkEligibilityTests(OfflineCase):
    def test_current_country_governs_geography_without_rewriting_saved_brief(self):
        old_brief = qualification.search_brief(self.profile, self.now)
        unchanged = copy.deepcopy(old_brief)
        self.profile["eligible_countries"] = ["DE"]
        self.profile["location_pattern"] = "Germany|Berlin"
        self.profile["work_location_policy"] = location_policy("DE", "local_employee")
        self.review["geography"] = {"eligible": True, "eligible_from": ["DE"], "evidence": "Exact synthetic role permits German employment"}
        self.review["work_eligibility"] = eligibility_review(self.job, self.now, "DE", "local_employee")
        direct = qualification.qualify(self.job, self.review, old_brief, self.now, {"opportunities": []}, {"records": []}, profile=self.profile)
        self.assertTrue(direct["qualified"], direct["verification_gaps"])
        self.assertEqual(old_brief, unchanged)
        records.save(self.work / "profile.json", self.profile)
        run = {"id": "saved-canadian-run", "search_brief": old_brief}
        records.save(self.work / "data/jobs.json", {"opportunities": [{**self.job, "review": self.review}], "search_runs": [run]})
        before = (self.work / "data/jobs.json").read_bytes()
        rendered = read_page(render.render(self.work))[1]
        self.assertTrue(rendered["jobs"][0]["review"]["qualified"])
        for fields in ({"search_run_id": run["id"]}, {"search_brief": old_brief}):
            records.save(self.work / "country-request.json", {"opportunity_id": self.job["id"], "language": "en", "role": "development", **fields})
            process = subprocess.run([sys.executable, "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", "country-request.json", "--output", "country-packet.json"], capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            packet = records.load(self.work / "country-packet.json")
            self.assertTrue(packet["decision"]["qualified"])
            for key in ("window_start", "window_end", "source_windows", "requested_minimum", "manual_source_freshness_hours"):
                self.assertEqual(packet["search_brief"][key], old_brief[key])
            self.assertEqual(packet["submission_state"], "not_sent")
        self.assertEqual((self.work / "data/jobs.json").read_bytes(), before)

    def test_empty_policy_inherits_no_country_and_fails_before_collection(self):
        for policy in (None, {}):
            profile = copy.deepcopy(self.profile)
            profile["work_location_policy"] = policy
            result = work_eligibility.assess(self.job, self.review, self.now, profile)
            self.assertFalse(result["passed"])
            self.assertIsNone(result["policy"]["base_country"])
            self.assertIsNone(result["policy"]["work_path"])
            records.save(self.work / "profile.json", profile)
            with patch.object(scan, "collect_boards", side_effect=AssertionError("Collection forbidden in setup validation test")) as collect:
                with self.assertRaisesRegex(ValueError, "base_country"):
                    scan.scan(self.work, network=True)
                collect.assert_not_called()

    def test_two_country_path_policies_require_their_own_evidence(self):
        for country, path in (("CA", "remote_contract"), ("DE", "local_employee")):
            profile = copy.deepcopy(self.profile)
            profile["work_location_policy"] = location_policy(country, path)
            review = copy.deepcopy(self.review)
            review["work_eligibility"] = eligibility_review(self.job, self.now, country, path)
            self.assertTrue(work_eligibility.assess(self.job, review, self.now, profile)["passed"])
            for mismatch in ({"base_country": "AU"}, {"work_path": "different_path"}):
                wrong = copy.deepcopy(review)
                wrong["work_eligibility"]["work_path"].update(mismatch)
                self.assertFalse(work_eligibility.assess(self.job, wrong, self.now, profile)["passed"])
        self.assertFalse(work_eligibility.assess(self.job, self.review, self.now)["passed"])

    def test_identity_alias_pairs_and_explicit_unknown_handling(self):
        self.job["source_aliases"] = [{"id": "alias-a", "url": "https://fixture.invalid/a"}, {"id": "alias-b", "url": "https://fixture.invalid/b"}]
        review = copy.deepcopy(self.review)
        review["work_eligibility"].update(opportunity_id="alias-a", listing_url="https://fixture.invalid/b", source_url="https://fixture.invalid/b")
        self.assertFalse(self.evaluate(review)["checks"]["work_eligibility"])
        review["work_eligibility"].update(listing_url="https://fixture.invalid/a", source_url="https://fixture.invalid/a")
        self.assertTrue(self.evaluate(review)["checks"]["work_eligibility"])
        self.profile["work_location_policy"]["unknown_eligibility"] = "exclude"
        review.pop("work_eligibility")
        self.assertEqual(self.evaluate(review)["decision"], "excluded")

    def setUp(self):
        super().setUp()
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.profile["eligible_countries"] = ["CA"]
        self.profile["location_pattern"] = "Canada|Toronto"
        self.profile["work_location_policy"] = location_policy("CA", "remote_contract")
        records.save(self.work / "profile.json", self.profile)
        self.job = opportunity(location="Toronto, Canada")
        self.review = {
            "fit": "strong", "full_description_read": True, "duplicate_checked": True, "cv_file": "fixture.pdf",
            "degree_status": "not_stated", "degree_evidence": "Full fixture ad has no degree clause",
            "requirements": [{"requirement": ".NET Angular", "met": True, "evidence": "Fixture experience"}],
            "role": {"track": "development", "confirmed": True, "evidence": "Development duties"},
            "stack": {"dotnet": True, "angular": True, "evidence": "Both substantive"},
            "geography": {"eligible": True, "eligible_from": ["CA"], "evidence": "Synthetic Canadian path"},
            "route": {"status": "form_observed", "checked_at": self.now.isoformat(), "job_identifier": self.job["job_id"], "source_url": self.job["url"], "evidence": "Exact vacancy form"},
            "publication": {"kind": "original", "at": (self.now - dt.timedelta(hours=4)).isoformat(), "source_url": self.job["url"], "evidence": "Exact original timestamp"},
            "work_eligibility": eligibility_review(self.job, self.now, "CA", "remote_contract"),
        }
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        (self.work / "fixture.pdf").write_bytes(b"Fixture CV")
        records.save(self.work / "cv-manifest.json", {"versions": [{"version_id": "fixture", "language": "en", "roles": ["development"], "path": "fixture.pdf", "selection_status": "current"}]})

    def evaluate(self, review=None):
        return render.effective_review(self.job, review or self.review, self.profile, self.now, {"opportunities": []}, {"records": []})

    def constraint(self, kind, country="US", **changes):
        return {"kind": kind, "country": country, "mandatory": True, "scope": "all_paths", "office_only": kind == "office_presence", "evidence": "Full exact role requires this condition for the stated work location", **changes}

    def test_mandatory_foreign_conditions_exclude_even_with_full_technical_score(self):
        for kind in ("work_visa", "work_permit", "right_to_work", "residency", "relocation", "office_presence"):
            with self.subTest(kind=kind):
                review = copy.deepcopy(self.review)
                review["work_eligibility"]["constraints"] = [self.constraint(kind)]
                review["work_eligibility"]["sponsorship"] = "available"
                review["work_eligibility"]["no_sponsorship"] = True
                result = self.evaluate(review)
                self.assertTrue(result["score"]["passes"])
                self.assertEqual(result["decision"], "excluded")
                self.assertFalse(result["checks"]["work_eligibility"])

    def test_global_configured_path_and_foreign_publisher_can_pass_with_limits(self):
        self.job.update(publisher_country="US", company_country="GB", work_model_stated="Remote")
        result = self.evaluate()
        self.assertTrue(result["qualified"])
        self.assertIn("not employer confirmation", result["work_eligibility_check"]["limitation"])
        self.review["work_eligibility"].update(authorization_basis="explicit_no_foreign_requirement", authorization_evidence="Exact vacancy explicitly permits configured-country work without foreign authorization or relocation")
        result = self.evaluate()
        self.assertTrue(result["qualified"])
        self.assertEqual(result["work_eligibility_check"]["evidence_level"], "explicit_role_statement")

    def test_optional_sponsorship_or_separate_foreign_path_does_not_veto_configured_route(self):
        self.review["work_eligibility"].update(sponsorship="optional", relocation="optional")
        self.review["work_eligibility"].update(no_sponsorship=True, sponsorship_question="Will you now or later need sponsorship?")
        self.review["work_eligibility"]["constraints"] = [self.constraint("work_visa", mandatory=False)]
        self.assertTrue(self.evaluate()["qualified"])
        self.review["work_eligibility"]["constraints"] = [self.constraint("relocation", scope="alternative_only", alternative_path_evidence="The ad explicitly offers an independent configured-country route; relocation belongs only to the optional US-office path")]
        self.assertTrue(self.evaluate()["qualified"])
        self.review["work_eligibility"]["constraints"][0].pop("alternative_path_evidence")
        self.assertFalse(self.evaluate()["qualified"])

    def test_foreign_onboarding_visit_is_unresolved_not_invented_visa_requirement(self):
        self.review["work_eligibility"]["constraints"] = [self.constraint("office_presence", country="PL", office_only=False, evidence="The exact role requires a first-day office visit; travel/authorization conditions are not established")]
        result = self.evaluate()
        self.assertEqual(result["decision"], "needs_clarification")
        self.assertEqual(result["hard_exclusions"], [])

    def test_unknown_or_potential_requirement_never_qualifies(self):
        changes = [lambda r: r.pop("work_eligibility"), lambda r: r["work_eligibility"].update(authorization_basis="unknown"),
                   lambda r: r["work_eligibility"].update(full_ad_reviewed=False), lambda r: r["work_eligibility"].update(constraints_checked=False),
                   lambda r: r["work_eligibility"].update(constraints=[self.constraint("right_to_work", mandatory="unknown")]),
                   lambda r: r["work_eligibility"]["work_path"].update(status="unknown")]
        for mutate in changes:
            review = copy.deepcopy(self.review)
            mutate(review)
            result = self.evaluate(review)
            self.assertEqual(result["decision"], "needs_clarification")
            self.assertFalse(result["qualified"])

    def test_generic_unrelated_or_incomplete_evidence_cannot_clear_eligibility(self):
        for change in ({"source_url": "https://fixture.invalid/platform/country/canada"}, {"opportunity_id": "different"}, {"listing_url": "https://fixture.invalid/other-job"}, {"observed_at": (self.now + dt.timedelta(hours=1)).isoformat()}, {"evidence": " "}, {"authorization_evidence": ""}):
            review = copy.deepcopy(self.review)
            review["work_eligibility"].update(change)
            self.assertFalse(self.evaluate(review)["qualified"])

    def test_domestic_role_does_not_infer_foreign_law_or_candidate_permits(self):
        self.review["work_eligibility"]["constraints"] = [self.constraint("office_presence", country="CA")]
        self.assertTrue(self.evaluate()["qualified"])
        self.review["work_eligibility"].update(authorization_basis="unknown", no_sponsorship=True)
        result = self.evaluate()
        self.assertEqual(result["decision"], "needs_clarification")
        self.assertEqual(result["hard_exclusions"], [])

    def test_top_level_conflict_cannot_be_hidden_by_positive_review(self):
        self.job["work_eligibility"] = copy.deepcopy(self.review["work_eligibility"])
        self.job["work_eligibility"]["constraints"] = [self.constraint("right_to_work")]
        self.assertEqual(self.evaluate()["decision"], "excluded")

    def test_exact_linked_form_restriction_keeps_real_source_url(self):
        form = "https://fixture.invalid/apply/123456"
        self.review["route"].update(source_url=form, listing_url=self.job["url"], employer=self.job["company"], navigation_evidence="Exact vacancy Apply link opens this form")
        self.review["work_eligibility"].update(source_url=form, constraints=[self.constraint("right_to_work")])
        result = self.evaluate()
        self.assertEqual(result["decision"], "excluded")
        self.assertEqual(result["work_eligibility_check"]["assessments"][0]["source_url"], form)
        for change in ({"employer": "Unrelated employer"}, {"listing_url": "https://fixture.invalid/unrelated"}, {"job_identifier": "other-id"}, {"navigation_evidence": ""}):
            review = copy.deepcopy(self.review)
            review["route"].update(change)
            result = self.evaluate(review)
            self.assertFalse(result["qualified"])
            self.assertEqual(result["work_eligibility_check"]["hard_exclusions"], [])

    def test_network_admission_cannot_pass_even_with_positive_fit_flags(self):
        self.assertTrue(self.evaluate()["qualified"])
        self.job["record_kind"] = "source_access"
        self.job["response_mode"] = "network_admission"
        result = self.evaluate()
        self.assertTrue(result["score"]["passes"])
        self.assertFalse(result["qualified"])
        self.assertIn("not an identified opportunity", " ".join(result["hard_exclusions"]))

    def test_exact_agency_vacancy_screening_is_not_generic_intake(self):
        self.job["response_mode"] = "agency_screening"
        self.assertTrue(self.evaluate()["qualified"])
        records.save(self.work / "data/jobs.json", {"opportunities": [{**self.job, "review": self.review}]})
        packet = packets.prepare_packet(self.work, self.job, self.review, qualification.search_brief(self.profile, self.now), self.now, "en", "development", drafts=[{"recipient_type": "agency", "stage": "agency_screening", "text": "Local draft about the exact opening."}])
        self.assertTrue(packet["decision"]["qualified"])
        self.assertEqual(packet["drafts"][0]["stage"], "agency_screening")
        self.assertEqual(packet["submission_state"], "not_sent")
        for kind in ("source_access", "generic_screening"):
            self.job["record_kind"] = kind
            self.assertFalse(self.evaluate()["qualified"])
        self.job.pop("record_kind")
        self.job["response_mode"] = "generic_agency_screening"
        self.assertFalse(self.evaluate()["qualified"])

    def test_linked_project_proposal_form_qualifies_and_wrong_identity_does_not(self):
        self.job["type"] = "project"
        form = "https://fixture.invalid/proposal/123456"
        self.review["route"].update(status="proposal_observed", source_url=form, listing_url=self.job["url"], employer=self.job["company"], navigation_evidence="Exact project Submit Proposal link opens this destination")
        self.review["work_eligibility"]["source_url"] = form
        self.assertTrue(self.evaluate()["qualified"])
        records.save(self.work / "data/jobs.json", {"opportunities": [{**self.job, "review": self.review}]})
        self.assertTrue(read_page(render.render(self.work))[1]["jobs"][0]["review"]["qualified"])
        packet = packets.prepare_packet(self.work, self.job, self.review, qualification.search_brief(self.profile, self.now), self.now, "en", "development", drafts=[{"text": "I have attached my CV."}])
        self.assertTrue(packet["decision"]["qualified"])
        self.assertEqual(packet["submission_state"], "not_sent")
        self.assertFalse(packet["drafts"][0]["review"]["ready_for_use"])
        records.save(self.work / "local-packet.json", packet)
        self.assertEqual(records.load(self.work / "local-packet.json")["decision"]["work_eligibility_check"]["assessments"][0]["source_url"], form)
        for change in ({"job_identifier": "other"}, {"employer": "Other client"}, {"navigation_evidence": ""}):
            review = copy.deepcopy(self.review);review["route"].update(change)
            self.assertFalse(self.evaluate(review)["checks"]["work_eligibility"])
        self.job["type"] = "employment"
        result = self.evaluate()
        self.assertFalse(result["checks"]["route"])
        self.assertFalse(result["checks"]["work_eligibility"])

    def test_renderer_and_unsent_packet_use_current_preference_not_old_run(self):
        self.review["work_eligibility"]["constraints"] = [self.constraint("work_visa")]
        old_run = {"id": "before-preference", "window_start": (self.now - dt.timedelta(hours=24)).isoformat(), "window_end": self.now.isoformat(), "search_brief": {"work_location_policy": {"exclude_required_foreign_conditions": []}}}
        records.save(self.work / "data/jobs.json", {"opportunities": [{**self.job, "review": self.review}], "search_runs": [old_run]})
        before = [(self.work / p).read_bytes() for p in ("data/jobs.json", "data/applied_jobs.json")]
        row = read_page(render.render(self.work))[1]["jobs"][0]
        self.assertEqual(row["review"]["decision"], "excluded")
        for request_fields in ({"search_run_id": old_run["id"]}, {"search_brief": {**old_run["search_brief"], "window_start": old_run["window_start"], "window_end": old_run["window_end"]}}):
            records.save(self.work / "request.json", {"opportunity_id": self.job["id"], "language": "en", "role": "development", **request_fields})
            process = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", str(self.work / "request.json"), "--output", str(self.work / "packet.json")], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(process.returncode, 0, process.stderr)
            packet = records.load(self.work / "packet.json")
            self.assertEqual(packet["decision"]["decision"], "excluded")
            self.assertEqual(packet["submission_state"], "not_sent")
            self.assertEqual(packet["search_brief"]["window_start"], old_run["window_start"])
        self.assertEqual([(self.work / p).read_bytes() for p in ("data/jobs.json", "data/applied_jobs.json")], before)
        self.profile["work_location_policy"] = location_policy("DE", "local_employee")
        records.save(self.work / "profile.json", self.profile)
        rendered = read_page(render.render(self.work))[1]
        self.assertEqual(rendered["search_brief"]["window_start"], old_run["window_start"])
        self.assertEqual(rendered["jobs"][0]["review"]["decision"], "needs_clarification")
        for fields in ({"search_run_id": old_run["id"]}, {"search_brief": {**old_run["search_brief"], "window_start": old_run["window_start"], "window_end": old_run["window_end"]}}):
            records.save(self.work / "request.json", {"opportunity_id": self.job["id"], "language": "en", "role": "development", **fields})
            process = subprocess.run([sys.executable, "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", "request.json", "--output", "changed-policy.json"], capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            packet = records.load(self.work / "changed-policy.json")
            self.assertEqual(packet["decision"]["decision"], "needs_clarification")
            self.assertEqual(packet["decision"]["work_eligibility_check"]["policy"]["base_country"], "DE")
            self.assertEqual(packet["search_brief"]["window_start"], old_run["window_start"])
        self.assertEqual([(self.work / p).read_bytes() for p in ("data/jobs.json", "data/applied_jobs.json")], before)
