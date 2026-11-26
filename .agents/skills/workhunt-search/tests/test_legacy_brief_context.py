"""Synthetic copied-brief context regression; no private Git history or generator."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from test_kit import eligibility_review, OfflineCase, opportunity
import packets
import qualification
import records


class LegacyBriefContextTests(OfflineCase):
    def setUp(self):
        super().setUp()
        path = Path(__file__).parent / "fixtures/legacy-collector-synthetic.json"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "ac52239e1d98d073323fb7d8375b60ffb21720fb7108a8efbb9336ae4e4a291f")
        self.fixture_data = records.load(path)
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.legacy = copy.deepcopy(self.fixture_data["search_brief"])
        # Only timestamps move; the hand-authored markerless legacy shape stays.
        self.legacy.update(window_end=self.now.isoformat(), window_start=(self.now - dt.timedelta(hours=24)).isoformat())
        self.profile["search_brief"]["manual_source_freshness_hours"] = {"employer_registry": 60, "techmap": 60}
        records.save(self.work / "profile.json", self.profile)
        self.job = opportunity()
        self.review = {
            "fit": "strong", "full_description_read": True, "duplicate_checked": True, "cv_file": "fixture.pdf",
            "degree_status": "not_stated", "degree_evidence": "Full fixture ad has no degree clause",
            "requirements": [{"requirement": ".NET Angular", "met": True, "evidence": "Fixture experience"}],
            "role": {"track": "development", "confirmed": True, "evidence": "Development duties"},
            "stack": {"dotnet": True, "angular": True, "evidence": "Both substantive"},
            "geography": {"eligible": True, "eligible_from": ["IL"], "evidence": "Synthetic country eligibility"},
            "work_eligibility": eligibility_review(self.job, self.now),
            "route": {"status": "form_observed", "checked_at": self.now.isoformat(), "job_identifier": self.job["job_id"], "source_url": self.job["url"], "evidence": "Exact vacancy form"},
            "publication": {"kind": "original", "at": (self.now - dt.timedelta(hours=48)).isoformat(), "source_url": self.job["url"], "evidence": "Exact original timestamp"},
            "source_membership": {"group": "employer_registry", "opportunity_id": self.job["id"], "listing_url": self.job["url"], "source_url": "https://fixture.invalid/board", "observed_at": self.now.isoformat(), "evidence": "Exact requisition observed on registry board"},
        }
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        (self.work / "fixture.pdf").write_bytes(b"Fixture CV")
        records.save(self.work / "cv-manifest.json", {"versions": [{"version_id": "fixture", "language": "en", "roles": ["development"], "path": "fixture.pdf", "selection_status": "current"}]})

    def legacy_run(self):
        return {"id": "old-collector", "search_brief": copy.deepcopy(self.legacy), "window_start": self.legacy["window_start"], "window_end": self.legacy["window_end"], "fixture_mode": False, "boards_attempted": 1, "source_checks": []}

    def packet(self, request_fields, runs):
        records.save(self.work / "data/jobs.json", {"opportunities": [{**self.job, "review": self.review}], "search_runs": runs})
        records.save(self.work / "request.json", {"opportunity_id": self.job["id"], "language": "en", "role": "development", **request_fields})
        paths = [self.work / "data/jobs.json", self.work / "data/applied_jobs.json"]
        before = [p.read_bytes() for p in paths]
        process = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", str(self.work / "request.json"), "--output", str(self.work / "packet.json")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual([p.read_bytes() for p in paths], before)
        return records.load(self.work / "packet.json")

    def evaluate(self, brief):
        return qualification.qualify(self.job, self.review, brief, self.now, {"opportunities": []}, {"records": []}, profile=self.profile)

    def test_synthetic_legacy_run_id_and_copied_brief_are_same_collector(self):
        self.assertNotIn("execution_context", self.legacy)
        self.assertNotIn("source_windows", self.legacy)
        self.assertEqual(self.legacy["manual_source_freshness_hours"]["employer_registry"], 60)
        by_id = self.packet({"search_run_id": "old-collector"}, [self.legacy_run()])
        by_copy = self.packet({"search_brief": self.legacy}, [self.legacy_run()])
        summaries = [{"context": p["search_brief"]["execution_context"], "window": p["decision"]["freshness_check"]["window"]["hours"], "freshness": p["decision"]["checks"]["freshness"], "qualified": p["decision"]["qualified"], "submission": p["submission_state"]} for p in (by_id, by_copy)]
        print("LEGACY_PACKET_COMPARISON " + json.dumps(summaries))
        self.assertEqual(summaries[0], summaries[1])
        self.assertEqual(summaries[1], {"context": "collector", "window": 24, "freshness": False, "qualified": False, "submission": "not_sent"})
        self.assertEqual(by_id["decision"]["freshness_check"]["window"], by_copy["decision"]["freshness_check"]["window"])

    def test_unmatched_legacy_load_preserves_base_bounds_without_dormant_widening(self):
        for hours in (24, 96):
            with self.subTest(hours=hours):
                saved = {**self.legacy, "window_start": (self.now - dt.timedelta(hours=hours)).isoformat()}
                brief = qualification.search_brief(self.profile, self.now, saved)
                self.assertEqual(brief["execution_context"], "unresolved")
                self.assertEqual(brief["window_start"], saved["window_start"])
                self.assertIn("unresolved", brief["context_provenance"]["status"])
                self.assertEqual(self.evaluate(brief)["freshness_check"]["window"]["hours"], hours)
                self.assertNotIn("employer_registry", brief["source_windows"])

    def test_current_new_and_marker_bearing_manual_snapshot_keep_configured_windows(self):
        new = qualification.search_brief(self.profile, self.now)
        modern = qualification.search_brief(self.profile, self.now, new)
        for brief in (new, modern):
            self.assertEqual(brief["execution_context"], "manual")
            self.assertEqual(self.evaluate(brief)["freshness_check"]["window"]["hours"], 60)
            self.assertTrue(self.evaluate(brief)["qualified"])
        notification = {**self.legacy, "run_type": "notification", "window_start": (self.now - dt.timedelta(hours=96)).isoformat()}
        brief = qualification.search_brief(self.profile, self.now, notification, saved_runs=[])
        self.assertEqual(brief["execution_context"], "notification")
        self.assertEqual(brief["context_provenance"]["status"], "recorded_run_type")
        self.assertEqual(self.evaluate(brief)["freshness_check"]["window"]["hours"], 24)
        self.assertFalse(self.evaluate(brief)["qualified"])
        unresolved_notification = qualification.search_brief(self.profile, self.now, {**notification, "execution_context": "unresolved"})
        self.assertEqual(self.evaluate(unresolved_notification)["freshness_check"]["window"]["hours"], 24)
        self.assertFalse(self.evaluate(unresolved_notification)["qualified"])
        for kind in ("assessment", "fixture"):
            brief = qualification.search_brief(self.profile, self.now, {**self.legacy, "run_type": kind}, saved_runs=[])
            self.assertEqual(brief["execution_context"], kind)
            self.assertEqual(brief["context_provenance"]["status"], "recorded_run_type")
        profile = copy.deepcopy(self.profile)
        profile["search_brief"]["execution_context"] = "collector"
        brief = qualification.search_brief(profile, self.now)
        self.assertEqual(brief["execution_context"], "collector")
        self.assertEqual(self.evaluate(brief)["freshness_check"]["window"]["hours"], 24)
        forced = qualification.search_brief(self.profile, self.now, self.legacy, execution_context="collector")
        self.assertEqual(forced["context_provenance"]["status"], "explicit_execution_context")

    def test_recovered_manual_context_alone_does_not_enact_legacy_preferences(self):
        run = {"id": "old-manual", "execution_context": "manual", "search_brief": self.legacy}
        packet = self.packet({"search_brief": self.legacy}, [run])
        self.assertEqual(packet["search_brief"]["execution_context"], "manual")
        self.assertEqual(packet["decision"]["freshness_check"]["window"]["hours"], 24)
        self.assertFalse(packet["decision"]["qualified"])
        by_id = self.packet({"search_run_id": "old-manual"}, [run])
        self.assertEqual(by_id["decision"]["freshness_check"], packet["decision"]["freshness_check"])

    def test_unresolved_source_evidence_is_preserved_separately_until_exact_recovery(self):
        saved = copy.deepcopy(self.legacy)
        saved["source_windows"] = {"employer_registry": {
            "hours": 60, "window_start": (self.now - dt.timedelta(hours=60)).isoformat(),
            "window_end": self.now.isoformat()}}
        original = copy.deepcopy(saved)
        unresolved = qualification.search_brief(self.profile, self.now, saved, saved_runs=[])
        self.assertEqual(saved, original)
        self.assertEqual(unresolved["recorded_source_windows"], saved["source_windows"])
        self.assertEqual(set(unresolved["source_windows"]), {"other"})
        self.assertEqual(unresolved["execution_context"], "unresolved")
        self.assertFalse(self.evaluate(unresolved)["checks"]["freshness"])
        run = {"id": "synthetic-enacted-windows", "search_brief": saved}
        recovered = qualification.search_brief(self.profile, self.now, saved, saved_runs=[run])
        self.assertEqual(recovered["context_provenance"], {"status": "canonical_snapshot_match", "matching_run_ids": [run["id"]]})
        self.assertTrue(self.evaluate(recovered)["checks"]["freshness"])
        self.assertEqual(qualification.brief_from_run(self.profile, self.now, run)["source_windows"], recovered["source_windows"])

    def test_conflicting_recorded_timezone_does_not_replace_supplied_snapshot(self):
        run = {"id": "synthetic-zone-conflict", "search_brief": self.legacy,
               "execution_context": "manual", "timezone": "America/Toronto"}
        profile = copy.deepcopy(self.profile)
        profile["timezone"] = "Asia/Tokyo"
        brief = qualification.search_brief(profile, self.now, self.legacy, saved_runs=[run])
        self.assertEqual(brief["execution_context"], "unresolved")
        self.assertEqual(brief["timezone"], "UTC")
        self.assertEqual(brief["window_start"], self.legacy["window_start"])
        self.assertEqual(brief["context_provenance"]["status"], "unresolved_conflicting_canonical_evidence")

    def test_json_and_packet_roundtrip_preserve_unresolved_evidence_without_authorizing_it(self):
        saved = copy.deepcopy(self.legacy)
        saved["source_windows"] = {"employer_registry": {
            "hours": 60, "window_start": (self.now - dt.timedelta(hours=60)).isoformat(),
            "window_end": self.now.isoformat()}}
        collector = {**self.legacy_run(), "search_brief": saved}
        manual = {"id": "conflicting-manual-peer", "execution_context": "manual", "search_brief": saved}
        first = self.packet({"search_brief": saved}, [collector, manual])
        first_brief = first["search_brief"]
        expected = {"status": "unresolved_conflicting_canonical_evidence", "matching_run_ids": [collector["id"], manual["id"]]}
        self.assertEqual(first_brief["context_provenance"], expected)
        self.assertEqual(first_brief["recorded_source_windows"], saved["source_windows"])
        records.save(self.work / "normalized-brief.json", first_brief)
        loaded = records.load(self.work / "normalized-brief.json")
        normalized = qualification.search_brief(self.profile, self.now, loaded, saved_runs=[collector, manual])
        by_id = qualification.brief_from_run(self.profile, self.now, {"id": "normalized-private-run", "search_brief": loaded})
        second = self.packet({"search_brief": loaded}, [collector, manual])
        for brief in (normalized, by_id, second["search_brief"]):
            self.assertEqual(brief["context_provenance"], expected)
            self.assertEqual(brief["recorded_source_windows"], saved["source_windows"])
            self.assertEqual(brief["execution_context"], "unresolved")
            self.assertEqual(set(brief["source_windows"]), {"other"})
            self.assertEqual(brief["source_windows"]["other"]["hours"], 24)
            self.assertFalse(self.evaluate(brief)["checks"]["freshness"])
        self.assertEqual(second["submission_state"], "not_sent")
        self.assertEqual(loaded, first_brief)

    def test_absent_source_window_evidence_stays_absent_on_json_and_packet_reload(self):
        collector = self.legacy_run()
        manual = {"id": "ambiguous-manual", "execution_context": "manual", "search_brief": self.legacy}
        first = self.packet({"search_brief": self.legacy}, [collector, manual])
        self.assertIsNone(first["search_brief"].get("recorded_source_windows"))
        records.save(self.work / "normalized-without-source-evidence.json", first["search_brief"])
        loaded = records.load(self.work / "normalized-without-source-evidence.json")
        direct = qualification.search_brief(self.profile, self.now, loaded)
        second = self.packet({"search_brief": loaded}, [collector, manual])
        canonical = qualification.brief_from_run(self.profile, self.now, {"id": "saved-normalized", "search_brief": loaded})
        for brief in (direct, canonical, second["search_brief"]):
            self.assertIsNone(brief.get("recorded_source_windows"))
            self.assertEqual(brief["context_provenance"], first["search_brief"]["context_provenance"])
            self.assertEqual(brief["execution_context"], "unresolved")
            self.assertEqual(set(brief["source_windows"]), {"other"})
            self.assertEqual(brief["source_windows"]["other"]["hours"], 24)
            self.assertFalse(self.evaluate(brief)["checks"]["freshness"])
        self.assertEqual(second["submission_state"], "not_sent")

    def test_conflicting_context_policy_or_bounds_do_not_choose_a_winner(self):
        manual = {"id": "manual-peer", "execution_context": "manual", "search_brief": self.legacy}
        for kind in ("context", "policy", "bounds"):
            with self.subTest(kind=kind):
                first, second = copy.deepcopy(manual), copy.deepcopy(manual)
                first["id"], second["id"] = "first", "second"
                if kind == "context":
                    first = self.legacy_run()
                elif kind == "policy":
                    first["source_windows"] = {"employer_registry": {"hours": 60, "window_start": (self.now - dt.timedelta(hours=60)).isoformat()}}
                    second["source_windows"] = {"employer_registry": {"hours": 48, "window_start": (self.now - dt.timedelta(hours=48)).isoformat()}}
                else:
                    first["window_start"] = (self.now - dt.timedelta(hours=96)).isoformat()
                    second = None
                runs = [first, second] if second else [first]
                packet = self.packet({"search_brief": self.legacy}, runs)
                self.assertEqual(packet["search_brief"]["execution_context"], "unresolved")
                self.assertEqual(packet["search_brief"]["window_start"], self.legacy["window_start"])
                self.assertFalse(packet["decision"]["checks"]["freshness"])
                self.assertEqual(packet["submission_state"], "not_sent")
