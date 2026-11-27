"""Offline regressions for buyer-requested Svelte work, never a live listing claim."""
import copy
import datetime as dt
import json
from unittest.mock import patch

from test_kit import OfflineCase, board, eligibility_review, gh_row, read_page, location_policy
import discovery_routes
import opportunity_types
import packets
import qualification
import records
import render
import scan


class ProjectPolicyTests(OfflineCase):
    def test_enabled_policy_validation_stops_before_any_network_or_collection(self):
        import profile_config
        valid = self.profile["search_brief"]["project_stack_policy"]
        policies = [{"configured": True}, {"configured": True, "alternatives": []}, {"configured": True, "alternatives": "invalid"}]
        for patterns in (None, {}, {"ui": ""}, {"ui": ".*"}, {"ui": r"\w+"}, {"ui": "["}):
            policy = copy.deepcopy(valid)
            policy["alternatives"][0]["discovery_patterns"] = patterns
            policies.append(policy)
        with patch.object(scan, "collect_boards", side_effect=AssertionError("Collection forbidden")) as collect, patch.object(scan, "get", side_effect=AssertionError("Network forbidden")) as network:
            for policy in policies:
                profile = copy.deepcopy(self.profile); profile["search_brief"]["project_stack_policy"] = policy
                records.save(self.work / "profile.json", profile)
                with self.assertRaisesRegex(ValueError, "project_stack_policy"):
                    scan.scan(self.work, network=True)
            collect.assert_not_called(); network.assert_not_called()
        self.assertFalse((self.work / "runs").exists())
        for policy in (None, {}, {"configured": False, "alternatives": [], "provenance": {}}, {"angular_frontend_without_dotnet": False}, {"angular_frontend_without_dotnet": True}, valid):
            profile = copy.deepcopy(self.profile)
            if policy is None:
                profile["search_brief"].pop("project_stack_policy")
            else:
                profile["search_brief"]["project_stack_policy"] = policy
            self.assertIs(profile_config.validate_profile(profile), profile)
    def test_two_explicit_capability_schemes_control_discovery_and_qualification(self):
        original = copy.deepcopy(self.profile)
        self.assertTrue(self.assess()["qualified"])
        data_policy = {"configured": True, "alternatives": [{"id": "data-work", "required_capabilities": ["data"], "discovery_patterns": {"data": r"\bPolars\b"}}], "provenance": {"evidence": "Second synthetic explicit choice"}}
        self.profile["search_brief"]["project_stack_policy"] = data_policy
        self.assertFalse(self.assess()["checks"]["stack"])
        job = {**self.job, "description": "Buyer requests paid Polars data transformation"}
        review = copy.deepcopy(self.review)
        review["stack"] = {"data": True, "evidence": "Exact buyer asks for data transformation"}
        review["project_scope"]["capabilities"] = {"data": True}
        review["project_scope"]["deliverables"] = ["Implement requested transformation"]
        result = self.assess(job, review)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["stack_check"]["alternative_id"], "data-work")
        self.assertIn("projects", scan.classify(job, self.profile)["tracks"])
        self.assertNotIn("projects", scan.classify(job, original)["tracks"])
        self.assertEqual(result["score"]["total"], 4)

    def test_empty_malformed_or_explicitly_disabled_policy_never_enables_an_alternative(self):
        for policy in (None, {}, [], {"unknown": True}, {"angular_frontend_without_dotnet": False},
                       {"configured": False, "angular_frontend_without_dotnet": True},
                       {"alternatives": [], "angular_frontend_without_dotnet": True},
                       {"configured": True, "alternatives": None, "angular_frontend_without_dotnet": True}):
            brief = qualification.search_brief(self.profile, self.now)
            brief["project_stack_policy"] = policy
            self.assertFalse(self.assess(brief=brief)["checks"]["stack"])
            self.assertEqual(opportunity_types.project_alternatives(policy), [])
        for patterns in ({}, {"ui": " "}, {"ui": ".*"}, {"ui": "["}):
            policy = copy.deepcopy(self.profile["search_brief"]["project_stack_policy"])
            policy["alternatives"][0]["discovery_patterns"] = patterns
            self.assertEqual(opportunity_types.project_alternatives(policy), [])

    def test_legacy_choice_and_scope_translate_only_without_explicit_generic_override(self):
        profile = copy.deepcopy(self.profile)
        profile["search_brief"]["project_stack_policy"] = {"angular_frontend_without_dotnet": True, "provenance": {"evidence": "Synthetic historical adoption"}}
        profile["matching_aliases"] = [{"pattern": "אנגולר", "replacement": "Angular"}]
        job = {**self.job, "description": "Buyer requests paid Angular frontend work"}
        review = copy.deepcopy(self.review)
        review["stack"] = {"angular": True, "dotnet": False, "evidence": "Exact buyer brief"}
        review["project_scope"].pop("capabilities")
        review["project_scope"]["angular_frontend"] = True
        saved = qualification.search_brief(profile, self.now)
        before = json.dumps(saved, sort_keys=True)
        self.assertTrue(self.assess(job, review, saved)["qualified"])
        self.assertEqual(before, json.dumps(saved, sort_keys=True))
        for capabilities in ({}, {"angular": False}, {"other": True}, None):
            explicit = copy.deepcopy(review); explicit["project_scope"]["capabilities"] = capabilities
            self.assertFalse(self.assess(job, explicit, saved)["checks"]["stack"])
        for title in ("Angular18 Developer", "AngularJS Developer", "מפתח אנגולר"):
            lead = {**job, "title": title, "description": "", "description_complete": False}
            self.assertIn("projects", scan.classify(lead, profile)["tracks"])
        profile["search_brief"]["project_stack_policy"]["angular_frontend_without_dotnet"] = False
        self.assertFalse(self.assess(job, review, qualification.search_brief(profile, self.now))["checks"]["stack"])
        self.assertTrue(self.assess(job, review, qualification.search_brief(profile, self.now, saved=saved))["qualified"])

    def test_nonblank_buyer_and_stack_evidence_and_anonymous_pairing(self):
        for key, value in (("evidence", " "), ("deliverables", [" "]), ("source_url", " ")):
            review = copy.deepcopy(self.review); review["project_scope"][key] = value
            self.assertFalse(self.assess(review=review)["checks"]["stack"])
        review = copy.deepcopy(self.review); review["stack"]["evidence"] = " "
        self.assertFalse(self.assess(review=review)["checks"]["stack"])
        form = "https://example.invalid/proposal/fixture"
        for project_id in (None, " ", "wrong"):
            review = copy.deepcopy(self.review)
            review["route"].update(source_url=form, listing_url=self.job["source_url"], project_id=project_id, navigation_evidence="Exact project link to form")
            review["work_eligibility"]["source_url"] = form
            result = self.assess(review=review)
            self.assertFalse(result["checks"]["route"])
            self.assertFalse(result["checks"]["work_eligibility"])

    def test_cv_capabilities_do_not_adopt_policy_and_only_user_decision_records_provenance(self):
        from test_release import setup, ROOT, hashes
        before = hashes(ROOT / "templates")
        ledger = {"sources": [{"id": "cv", "kind": "synthetic_cv"}], "facts": [{"id": "skill", "source_id": "cv", "locator": "Skills", "kind": "cv_fact", "target": "capabilities", "value": {"name": "Svelte"}}], "decisions": [], "conflicts": []}
        profile, _ = setup.map_ledger(ledger)
        self.assertEqual(profile["search_brief"]["project_stack_policy"], {"configured": False, "alternatives": [], "provenance": {}})
        ledger["facts"][0]["target"] = "search_brief"
        with self.assertRaises(ValueError):
            setup.map_ledger(ledger)
        ledger["facts"] = []
        ledger["decisions"] = [{"target": "search_brief", "kind": "user_confirmation", "source_id": "cv", "locator": "Separate explicit preference", "evidence": "Synthetic user explicitly selects this project alternative", "value": self.profile["search_brief"]}]
        profile, _ = setup.map_ledger(ledger)
        self.assertEqual(profile["search_brief"]["project_stack_policy"]["provenance"]["locator"], "Separate explicit preference")
        self.assertEqual(before, hashes(ROOT / "templates"))
    def setUp(self):
        super().setUp()
        self.now = dt.datetime.now(dt.timezone.utc)
        self.profile.update(eligible_countries=["CA"], location_pattern="Canada|Toronto", work_location_policy=location_policy("CA", "remote_contract"), matching_aliases=[])
        self.profile["limited_experience"]["go"] = 1
        self.profile["search_brief"]["project_stack_policy"] = {"configured": True, "alternatives": [{"id": "frontend", "required_capabilities": ["ui"], "discovery_patterns": {"ui": r"\bSvelte(?:JS|\d+)?\b"}}], "provenance": {"evidence": "Synthetic explicit preference"}}
        records.save(self.work / "profile.json", self.profile)
        # Mirrors canonical paid_project/source_job_id/source_url shape. Synthetic
        # identity and evidence only; no assertion about a real buyer or candidate.
        self.job = {"id": "freelancer:fixture-ui", "source": "freelancer",
                    "source_job_id": "fixture-ui", "type": "paid_project",
                    "source_url": "https://example.invalid/projects/ui/fixture",
                    "title": "Interactive dashboard", "description_complete": True,
                    "description": "Buyer requests paid Svelte frontend dashboard and API integration; existing Node.js backend.",
                    "location": "Remote from Canada", "board_key": board()["key"]}
        self.review = {"fit": "strong", "full_description_read": True,
                       "role": {"track": "projects", "confirmed": True, "evidence": "Concrete buyer deliverables"},
                       "stack": {"ui": True, "dotnet": False, "evidence": "Buyer requests Svelte frontend"},
                       "project_scope": {"paid_client_work": True, "capabilities": {"ui": True},
                                         "engagement_type": "client_project", "deliverables": ["Implement Svelte dashboard"],
                                         "source_url": self.job["source_url"], "evidence": "Exact full buyer brief"},
                       "requirements": [{"requirement": value, "met": i < 3, "evidence": "Synthetic supported CV evidence" if i < 3 else ""}
                                        for i, value in enumerate(["Svelte", "TypeScript", "REST integration", "Node.js backend"])],
                       "geography": {"eligible": True, "eligible_from": ["CA"], "evidence": "Full fixture explicitly permits Canada"},
                       "degree_status": "not_stated", "degree_evidence": "Full buyer brief has no degree requirement",
                       "publication_events": [{"kind": "original", "at": (self.now - dt.timedelta(hours=2)).isoformat(),
                                               "source_url": self.job["source_url"], "evidence": "Synthetic precise publication"}],
                       "route": {"status": "proposal_observed", "source_url": self.job["source_url"],
                                 "checked_at": self.now.isoformat(), "job_identifier": self.job["source_job_id"],
                                 "evidence": "Exact fixture project accepts proposals", "message_field": "observed"},
                       "duplicate_checked": True, "cv_file": "fixture-cv.txt"}
        self.review["work_eligibility"] = eligibility_review({**self.job, "url": self.job["source_url"]}, self.now, "CA", "remote_contract")
        self.found, self.applied = {"opportunities": []}, {"records": []}

    def assess(self, job=None, review=None, brief=None):
        return qualification.qualify(job or self.job, review or self.review,
                                     brief or qualification.search_brief(self.profile, self.now),
                                     self.now, self.found, self.applied, profile=self.profile)

    def test_generic_title_and_paid_project_alias_enter_discovery_without_client_name(self):
        for kind in ("project", "paid_project", "contract"):
            with self.subTest(kind=kind):
                job = {**self.job, "type": kind, "review": self.review}
                result = scan.classify(job, self.profile)
                self.assertIn("projects", result["tracks"])
                self.assertEqual(result["track_match_kind"], "identified_project_stack_hint")
                self.assertNotIn("development", result["tracks"])

    def test_incomplete_ui_project_title_is_a_provisional_lead(self):
        job = {key: value for key, value in self.job.items() if key != "description"}
        job.update(title="Svelte Developer for Interactive Website", description_complete=False)
        result = scan.classify(job, self.profile)
        self.assertIn("projects", result["tracks"])
        self.assertEqual(result["track_match_kind"], "provisional_project_hint")
        self.assertFalse(self.assess(job)["qualified"])

    def test_discovery_accepts_explicitly_configured_capability_spellings(self):
        for title in ("Svelte18 Developer", "SvelteJS Developer", "Svelte Developer"):
            job = {**self.job, "title": title, "description": "", "description_complete": False}
            self.assertIn("projects", scan.classify(job, self.profile)["tracks"])
        self.assertNotIn("projects", scan.classify({**self.job, "title": "React Developer", "description": "React frontend"}, self.profile)["tracks"])

    def test_paid_project_75_percent_without_dotnet_in_all_new_brief_modes(self):
        for mode in ("manual", "assessment", "notification", "fixture", "collector"):
            with self.subTest(mode=mode):
                profile = copy.deepcopy(self.profile)
                profile["search_brief"]["run_type"] = "manual" if mode == "collector" else mode
                result = self.assess(brief=qualification.search_brief(profile, self.now, execution_context=mode))
                self.assertTrue(result["qualified"], result["verification_gaps"])
                self.assertEqual(result["stack_check"]["path"], "client_project_alternative")
                self.assertEqual((result["score"]["supported"], result["score"]["total"]), (3, 4))
                self.assertEqual(result["score"]["gaps"], ["Node.js backend"])

    def test_explicit_project_contract_passes_employee_contract_does_not(self):
        job = {**self.job, "type": "contract"}
        self.assertTrue(self.assess(job)["qualified"])
        review = copy.deepcopy(self.review)
        review["project_scope"].pop("engagement_type")
        self.assertFalse(self.assess(job, review)["checks"]["stack"])

    def test_employment_and_dotnet_only_do_not_gain_an_alternative(self):
        self.assertFalse(self.assess({**self.job, "type": "employment"})["checks"]["stack"])
        review = copy.deepcopy(self.review)
        review["stack"].update(ui=False, dotnet=True)
        self.assertFalse(self.assess(review=review)["checks"]["stack"])

    def test_tags_bidder_text_unrelated_source_and_source_access_do_not_prove_scope(self):
        for change in ({"paid_client_work": False}, {"capabilities": {"ui": False}}, {"evidence": ""},
                       {"deliverables": []}, {"source_url": "https://example.invalid/other"}):
            review = copy.deepcopy(self.review)
            review["project_scope"].update(change)
            with self.subTest(change=change):
                self.assertFalse(self.assess(review=review)["checks"]["stack"])
        for kind in ("service", "profile", "source_access", "network_admission"):
            self.assertFalse(self.assess({**self.job, "record_kind": kind})["qualified"])
        review = copy.deepcopy(self.review)
        review.pop("project_scope")
        self.assertFalse(self.assess(review=review)["checks"]["stack"])

    def test_scoring_and_hard_skill_exclusions_remain(self):
        review = copy.deepcopy(self.review)
        review["requirements"][2]["met"] = False
        self.assertFalse(self.assess(review=review)["qualified"])
        review = copy.deepcopy(self.review)
        review["degree_status"] = "mandatory_no_alternative"
        self.assertFalse(self.assess(review=review)["qualified"])
        review = copy.deepcopy(self.review)
        review["requirements"][-1].update(requirement="More than two years Go", technology="go", minimum_years=2)
        self.assertFalse(self.assess(review=review)["qualified"])

    def test_independent_gates_and_history_still_block(self):
        for key, value in (("route", {}), ("publication_events", []), ("work_eligibility", {}),
                           ("geography", {}), ("duplicate_checked", False)):
            review = copy.deepcopy(self.review)
            review[key] = value
            with self.subTest(key=key):
                self.assertFalse(self.assess(review=review)["qualified"])
        self.applied = {"records": [{"id": self.job["id"], "suppress_from_new_results": True}]}
        self.assertFalse(self.assess()["qualified"])

    def test_old_snapshots_do_not_silently_inherit_current_project_policy(self):
        legacy = copy.deepcopy(self.profile["search_brief"])
        legacy.pop("project_stack_policy")
        legacy["execution_context"] = "manual"
        before = copy.deepcopy(legacy)
        old = qualification.search_brief(self.profile, self.now, saved=legacy)
        self.assertNotIn("project_stack_policy", old)
        self.assertFalse(self.assess(brief=old)["qualified"])
        self.assertEqual(legacy, before)
        modern = qualification.search_brief(self.profile, self.now)
        profile = copy.deepcopy(self.profile)
        profile["search_brief"].pop("project_stack_policy")
        saved = qualification.search_brief(profile, self.now, saved=modern)
        self.assertTrue(self.assess(brief=saved)["qualified"])

    def test_anonymous_buyer_separate_proposal_form_requires_paired_project_id(self):
        review = copy.deepcopy(self.review)
        form = "https://example.invalid/proposals/fixture"
        review["route"].update(source_url=form, listing_url=self.job["source_url"],
                               project_id=self.job["source_job_id"], navigation_evidence="Exact project opened this proposal form")
        review["work_eligibility"]["source_url"] = form
        self.assertTrue(self.assess(review=review)["qualified"])
        review["route"].pop("project_id")
        result = self.assess(review=review)
        self.assertFalse(result["checks"]["route"])
        self.assertFalse(result["checks"]["work_eligibility"])

    def test_client_invitation_with_review_only_description_stays_compatible(self):
        job = {"id": "fixture", "url": self.job["source_url"], "company": "Buyer", "type": "project",
               "response_mode": "client_invitation"}
        self.assertTrue(opportunity_types.identified_project(job, {"description_evidence": "Exact buyer brief inspected"}))
        job["review"] = {"description_evidence": "Exact buyer brief inspected"}
        self.assertTrue(discovery_routes.opportunity_candidate(job))
        self.assertTrue(discovery_routes.opportunity_candidate({**self.job, "response_mode": "project_proposal"}))

    def test_collector_fixture_keeps_project_with_generic_title(self):
        with patch.object(scan, "normalize", return_value=[self.job]):
            run = self.fixture([{"board": board(), "jobs": [gh_row()]}])
        hits = records.load(run / "hits.json")
        self.assertEqual([hit["id"] for hit in hits], [self.job["id"]])

    def test_render_and_packet_share_policy_without_mutating_canonical_history(self):
        job = {**self.job, "review": copy.deepcopy(self.review), "project_scope": self.review["project_scope"]}
        job["review"].pop("project_scope")
        records.save(self.work / "data/jobs.json", {"opportunities": [job], "search_runs": []})
        records.save(self.work / "data/applied_jobs.json", self.applied)
        before = (self.work / "data/jobs.json").read_bytes()
        rendered = read_page(render.render(self.work))[1]
        self.assertEqual(rendered["qualified_count"], 1)
        self.assertEqual(rendered["jobs"][0]["review"]["stack_check"]["path"], "client_project_alternative")
        with patch.object(packets, "select_cv", return_value={"resolved_path": "fixture-cv.txt"}):
            packet = packets.prepare_packet(self.work, self.job, self.review, qualification.search_brief(self.profile, self.now),
                                            self.now, "en", "projects", drafts=[{"recipient_type": "client", "text": "Synthetic local draft"}])
        self.assertTrue(packet["decision"]["qualified"])
        self.assertEqual(packet["drafts"][0]["recipient_type"], "client")
        self.assertEqual(packet["submission_state"], "not_sent")
        self.assertEqual((self.work / "data/jobs.json").read_bytes(), before)
