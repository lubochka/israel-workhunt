"""Manual source-window integration; synthetic records and subprocesses only."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo
from test_kit import OfflineCase, opportunity, read_page, board, gh_row
import packets
import qualification
import records
import render
import scan


class ManualFreshnessTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.job = opportunity()
        self.profile["search_brief"]["manual_source_freshness_hours"] = {"employer_registry": 60, "techmap": 60}
        records.save(self.work / "profile.json", self.profile)
        self.review = {
            "fit": "strong", "full_description_read": True, "duplicate_checked": True,
            "degree_status": "not_stated", "degree_evidence": "Full fixture ad has no degree clause", "cv_file": "fixture.pdf",
            "requirements": [{"requirement": ".NET Angular", "met": True, "evidence": "Fixture experience"}],
            "role": {"track": "development", "confirmed": True, "evidence": "Development duties"},
            "stack": {"dotnet": True, "angular": True, "evidence": "Both substantive"},
            "geography": {"eligible": True, "eligible_from": ["IL"], "evidence": "Synthetic country eligibility"},
            "route": {"status": "form_observed", "checked_at": self.now.isoformat(), "job_identifier": self.job["job_id"], "source_url": self.job["url"], "evidence": "Exact vacancy form"},
            "publication": {"kind": "original", "at": (self.now - dt.timedelta(hours=48)).isoformat(), "source_url": self.job["url"], "evidence": "Exact publication timestamp"},
            "source_membership": self.membership(),
        }
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        cv = self.work / "fixture.pdf"
        cv.write_bytes(b"Fixture CV")
        records.save(self.work / "cv-manifest.json", {"versions": [{"version_id": "fixture", "language": "en", "roles": ["development"], "path": cv.name, "selection_status": "current", "sha256": hashlib.sha256(cv.read_bytes()).hexdigest()}]})

    def membership(self, group="employer_registry"):
        return {"group": group, "opportunity_id": self.job["id"], "listing_url": self.job["url"],
                "source_url": "https://fixture.invalid/board" if group == "employer_registry" else "https://fixture.invalid/software.csv",
                "observed_at": self.now.isoformat(), "evidence": "Exact fixture requisition and URL observed in this source group"}

    def evaluate(self, review=None, brief=None, now=None):
        return qualification.qualify(self.job, review or self.review, brief or qualification.search_brief(self.profile, self.now), now or self.now, {"opportunities": []}, {"records": []})

    def run_snapshot(self, hours=24, source_hours=None):
        run = {"id": "saved", "run_type": "manual", "window_start": (self.now - dt.timedelta(hours=hours)).isoformat(), "window_end": self.now.isoformat(), "requested_minimum": 10}
        if source_hours:
            run["source_windows"] = {group: {"hours": value, "window_start": (self.now - dt.timedelta(hours=value)).isoformat()} for group, value in source_hours.items()}
        return run

    def save_job(self, runs=None):
        records.save(self.work / "data/jobs.json", {"opportunities": [{**self.job, "review": self.review}], "search_runs": runs or []})

    def test_manual_48h_original_refresh_repost_and_feed_update(self):
        for group in ("employer_registry", "techmap"):
            for kind, genuine, expected in [("original", False, True), ("refresh", True, True), ("repost", True, True), ("refresh", False, False), ("source_updated", True, False)]:
                with self.subTest(group=group, kind=kind, genuine=genuine):
                    review = copy.deepcopy(self.review)
                    review["source_membership"] = self.membership(group)
                    review["publication"].update(kind=kind, genuine_publication_event=genuine)
                    result = self.evaluate(review)
                    self.assertEqual(result["qualified"], expected)
                    self.assertEqual(result["freshness_check"]["window"]["hours"], 60)
                    self.assertEqual(result["freshness_check"]["window"]["group"], group)

    def test_membership_needs_evidence_and_exact_paired_identity(self):
        for changes in ({"group": "ordinary"}, {"group": []}, {"group": {}}, {"evidence": " "}, {"evidence": True}, {"source_url": "not a public URL"}, {"opportunity_id": "other-job"}, {"listing_url": "https://fixture.invalid/other-job"}, {"observed_at": (self.now + dt.timedelta(hours=1)).isoformat()}):
            with self.subTest(changes=changes):
                review = copy.deepcopy(self.review)
                review["source_membership"].update(changes)
                result = self.evaluate(review)
                self.assertFalse(result["qualified"])
                self.assertEqual(result["freshness_check"]["window"]["hours"], 24)
        review = copy.deepcopy(self.review)
        review.pop("source_membership")
        self.job.update(provider="techmap", source_scope="techmap")
        self.assertFalse(self.evaluate(review)["qualified"])
        self.job["source_aliases"] = [{"id": "alias-a", "url": "https://fixture.invalid/a"}, {"id": "alias-b", "url": "https://fixture.invalid/b"}]
        review["source_membership"] = {**self.membership(), "opportunity_id": "alias-a", "listing_url": "https://fixture.invalid/b"}
        self.assertFalse(self.evaluate(review)["qualified"])
        review["source_membership"]["listing_url"] = "https://fixture.invalid/a"
        self.assertTrue(self.evaluate(review)["qualified"])

    def test_exact_60h_boundary_and_elapsed_time_across_israel_dst(self):
        end = dt.datetime(2026, 10, 25, 12, tzinfo=ZoneInfo("Asia/Jerusalem"))
        brief = qualification.search_brief(self.profile, end)
        for hours, expected in [(60, True), (60 + 1/3600, False), (48, True)]:
            review = copy.deepcopy(self.review)
            review["source_membership"]["observed_at"] = end.isoformat()
            review["route"]["checked_at"] = end.isoformat()
            review["publication"]["at"] = (end.astimezone(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()
            result = self.evaluate(review, brief, end)
            self.assertEqual(result["qualified"], expected)
            window = result["freshness_check"]["window"]
            self.assertEqual(records.timestamp(window["window_end"]).timestamp() - records.timestamp(window["window_start"]).timestamp(), 60 * 3600)

    def test_renderer_current_manual_48h_passes(self):
        self.save_job()
        _, data = read_page(render.render(self.work))
        self.assertTrue(data["jobs"][0]["review"]["qualified"])
        self.assertEqual(data["jobs"][0]["review"]["freshness_check"]["window"]["hours"], 60)

    def test_saved_source_windows_preserve_policy_and_anchor_despite_profile_change(self):
        run = self.run_snapshot(source_hours={"employer_registry": 60, "techmap": 60, "other": 24})
        self.save_job([run])
        first = read_page(render.render(self.work))[1]
        self.profile["search_brief"]["manual_source_freshness_hours"] = {"employer_registry": 24, "techmap": 24}
        records.save(self.work / "profile.json", self.profile)
        second = read_page(render.render(self.work))[1]
        self.assertTrue(first["jobs"][0]["review"]["qualified"])
        self.assertEqual(first["search_brief"], second["search_brief"])
        self.assertEqual(first["search_brief"]["source_windows"]["employer_registry"]["window_start"], run["source_windows"]["employer_registry"]["window_start"])

    def test_malformed_saved_source_anchor_fails_without_sliding(self):
        for changes in ({"window_end": (self.now + dt.timedelta(hours=1)).isoformat()}, {"window_start": "invalid"}, {"window_start": (self.now - dt.timedelta(hours=59)).isoformat()}):
            with self.subTest(changes=changes):
                run = self.run_snapshot(source_hours={"employer_registry": 60})
                run["source_windows"]["employer_registry"].update(changes)
                self.save_job([run])
                with self.assertRaisesRegex(ValueError, "Saved source window"):
                    render.render(self.work)

    def test_membership_observed_after_anchor_does_not_move_publication_window(self):
        anchor = self.now - dt.timedelta(hours=2)
        brief = qualification.search_brief(self.profile, anchor)
        result = self.evaluate(brief=brief)
        self.assertTrue(result["qualified"])
        self.assertEqual(records.timestamp(result["freshness_check"]["window"]["window_end"]), anchor)
        self.assertEqual(result["freshness_check"]["window"]["membership_evidence"]["observed_at"], self.now.isoformat())

    def test_old_run_never_inherits_profile60_and_explicit96_is_preserved(self):
        for hours, expected in [(24, False), (96, True)]:
            with self.subTest(hours=hours):
                run = self.run_snapshot(hours)
                self.save_job([run])
                data = read_page(render.render(self.work))[1]
                self.assertEqual(data["search_brief"]["window_start"], run["window_start"])
                self.assertEqual(data["jobs"][0]["review"]["qualified"], expected)
                self.assertEqual(data["jobs"][0]["review"]["freshness_check"]["window"]["hours"], hours)

    def test_notification_collector_and_legacy_scan_view_stay24(self):
        saved = {**self.profile["search_brief"], "run_type": "notification"}
        result = self.evaluate(brief=qualification.search_brief(self.profile, self.now, saved))
        self.assertFalse(result["qualified"])
        self.assertEqual(result["freshness_check"]["window"]["hours"], 24)
        run = self.fixture([{"board": board(), "jobs": [gh_row()]}])
        meta = records.load(run / "meta.json")
        self.assertEqual(meta["search_brief"]["execution_context"], "collector")
        legacy = self.work / "runs/legacy"
        legacy.mkdir(parents=True)
        records.save(legacy / "meta.json", {"fixture_mode": False, "checked_at": self.now.isoformat(), "search_brief": self.profile["search_brief"]})
        records.save(legacy / "hits.json", [{**self.job, "review": self.review}])
        data = read_page(render.render(self.work, run=legacy))[1]
        self.assertFalse(data["jobs"][0]["review"]["checks"]["freshness"])
        self.assertEqual(data["search_brief"]["execution_context"], "collector")
        legacy_canonical = {**self.run_snapshot(source_hours={"employer_registry": 60}), "boards_attempted": 1, "fixture_mode": False}
        self.save_job([legacy_canonical])
        data = read_page(render.render(self.work))[1]
        self.assertEqual(data["search_brief"]["execution_context"], "collector")
        self.assertFalse(data["jobs"][0]["review"]["checks"]["freshness"])
        records.save(self.work / "collector-request.json", {"opportunity_id": self.job["id"], "language": "en", "role": "development", "search_run_id": legacy_canonical["id"]})
        process = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", str(self.work / "collector-request.json"), "--output", str(self.work / "collector-packet.json")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        packet = records.load(self.work / "collector-packet.json")
        self.assertEqual(packet["search_brief"]["execution_context"], "collector")
        self.assertFalse(packet["decision"]["checks"]["freshness"])

    def test_packet_cli_current_and_explicit_saved_windows(self):
        for saved in (False, "run_id", "full_brief"):
            with self.subTest(saved=saved):
                run = self.run_snapshot(source_hours={"employer_registry": 60, "other": 24})
                self.save_job([run] if saved else [])
                request = {"opportunity_id": self.job["id"], "language": "en", "role": "development"}
                if saved == "run_id":
                    request["search_run_id"] = run["id"]
                elif saved == "full_brief":
                    request["search_brief"] = {key: value for key, value in run.items() if key != "id"}
                records.save(self.work / "request.json", request)
                command = [sys.executable, "-X", "utf8", "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", str(self.work / "request.json"), "--output", str(self.work / "packet.json")]
                before = (self.work / "data/jobs.json").read_bytes()
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                packet = records.load(self.work / "packet.json")
                self.assertTrue(packet["decision"]["qualified"])
                self.assertEqual(packet["decision"]["freshness_check"]["window"]["hours"], 60)
                self.assertEqual(packet["submission_state"], "not_sent")
                if saved:
                    self.assertEqual(packet["search_brief"]["window_end"], run["window_end"])
                self.assertEqual((self.work / "data/jobs.json").read_bytes(), before)

    def test_configured_iana_zone_survives_saved_policy_and_dst(self):
        zone = ZoneInfo("America/Toronto")
        self.profile["timezone"] = "America/Toronto"
        anchor = dt.datetime(2026, 11, 1, 12, tzinfo=zone)
        brief = qualification.search_brief(self.profile, anchor)
        window = brief["source_windows"]["employer_registry"]
        expected = (anchor.astimezone(dt.timezone.utc) - dt.timedelta(hours=60)).astimezone(zone)
        self.assertEqual(window["window_start"], expected.isoformat())
        self.assertNotEqual(expected.utcoffset(), anchor.utcoffset())
        run = {"id": "saved-zone", "search_brief": brief, "timezone": "America/Toronto"}
        self.profile["timezone"] = "Asia/Tokyo"
        self.profile["search_brief"]["manual_source_freshness_hours"] = {}
        restored = qualification.brief_from_run(self.profile, self.now, run)
        self.assertEqual(restored["timezone"], "America/Toronto")
        self.assertEqual(restored["source_windows"], brief["source_windows"])
        legacy = self.run_snapshot(hours=96)
        self.assertIsNone(qualification.brief_from_run(self.profile, self.now, legacy)["timezone"])

    def test_unsupported_membership_uses_saved_other_and_nonmanual_contexts_stay_short(self):
        run = self.run_snapshot(hours=96)
        brief = qualification.brief_from_run(self.profile, self.now, run)
        review = copy.deepcopy(self.review)
        review["source_membership"]["group"] = "unsupported"
        result = self.evaluate(review, brief)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["freshness_check"]["window"]["hours"], 96)
        for mode in ("collector", "notification", "assessment", "fixture"):
            nonmanual = qualification.search_brief(self.profile, self.now, {**self.profile["search_brief"], "run_type": "manual"}, execution_context=mode)
            self.assertFalse(self.evaluate(brief=nonmanual)["checks"]["freshness"])
            self.assertEqual(nonmanual["source_windows"]["other"]["hours"], 24)

    def test_packet_rejects_partial_null_conflicting_and_malformed_snapshots_without_writes(self):
        run = self.run_snapshot(source_hours={"employer_registry": 60})
        self.save_job([run])
        base = {"opportunity_id": self.job["id"], "language": "en", "role": "development"}
        variants = [{"search_brief": value} for value in (None, {}, {"window_end": self.now.isoformat()}, {"window_start": None, "window_end": self.now.isoformat()}, {"window_start": "invalid", "window_end": self.now.isoformat()})]
        variants += [{"search_brief": run, "search_run_id": run["id"]}, {"search_run_id": None}]
        before = (self.work / "data/jobs.json").read_bytes()
        for value in variants:
            records.save(self.work / "bad-request.json", {**base, **value})
            result = subprocess.run([sys.executable, "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", str(self.work / "bad-request.json"), "--output", str(self.work / "must-not-exist.json")], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.work / "must-not-exist.json").exists())
            self.assertEqual((self.work / "data/jobs.json").read_bytes(), before)

    def test_active_latest_and_explicit_run_selection_is_shared_by_renderer_and_packet(self):
        wide = {**self.run_snapshot(source_hours={"employer_registry": 60}), "id": "wide", "requested_minimum": 3}
        narrow = {**self.run_snapshot(), "id": "narrow", "requested_minimum": 8}
        self.save_job([wide, narrow])
        found = records.load(self.work / "data/jobs.json")
        found["active_run_id"] = "wide"
        records.save(self.work / "data/jobs.json", found)
        self.assertEqual(read_page(render.render(self.work))[1]["search_brief"]["requested_minimum"], 3)
        selected = read_page(render.render(self.work, search_run_id="narrow"))[1]
        self.assertEqual(selected["search_brief"]["requested_minimum"], 8)
        self.assertFalse(selected["jobs"][0]["review"]["checks"]["freshness"])
        records.save(self.work / "active-request.json", {"opportunity_id": self.job["id"], "language": "en", "role": "development"})
        result = subprocess.run([sys.executable, "-B", str(Path(packets.__file__)), "prepare", str(self.work), "--input", str(self.work / "active-request.json"), "--output", str(self.work / "active-packet.json")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(records.load(self.work / "active-packet.json")["search_brief"]["requested_minimum"], 3)
        found.pop("active_run_id")
        records.save(self.work / "data/jobs.json", found)
        self.assertEqual(read_page(render.render(self.work))[1]["search_brief"]["requested_minimum"], 8)
