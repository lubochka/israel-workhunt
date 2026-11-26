"""Offline selected-channel, draft-quality and optional outcome evidence contracts."""
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from test_kit import OfflineCase, SKILL
import discovery_routes as routes
import drafts
import outcomes
import qualification
import records


class ManualChannelTests(OfflineCase):

    def test_cli_retains_unselected_targets_in_route_ambiguity_checks(self):
        shared = self.work / "shared catalog"
        (shared / "sources").mkdir(parents=True)
        for name in ("opportunity-sources.json", "manual-discovery.json"):
            (shared / "sources" / name).write_bytes((self.root / "sources" / name).read_bytes())
        path = shared / "sources/manual-discovery.json"
        catalog = json.loads(path.read_text('utf-8'))
        employer = next(row for row in catalog["employer_fallbacks"] if row["id"] == "codevalue")
        catalog["employer_fallbacks"].append({"id": "synthetic-unselected", "name": "Synthetic Unselected", "manual_routes": copy.deepcopy(employer["manual_routes"])})
        path.write_text(json.dumps(catalog), encoding='utf-8')
        observation = {"target_id": "codevalue", "source_url": employer["manual_routes"][0]["url"], "method": "public_page",
                       "transport_status": "success", "content_kind": "opportunity_list", "observed_count": 2,
                       "scope_complete": True, "evidence": "Synthetic completed scope"}
        records.save(self.work / "ambiguous-observation.json", observation)
        before = {p: p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        process = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(Path(routes.__file__)), str(self.work), '--shared-root', str(shared),
                                  '--employer', 'CodeValue', '--observation', 'ambiguous-observation.json'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(set(result['coverage']), {'codevalue'})
        self.assertEqual(result['coverage']['codevalue']['status'], 'not_attempted')
        self.assertEqual(result['coverage']['codevalue']['ignored_observation'], observation)
        self.assertTrue(result['fallbacks']['codevalue']['next_routes'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob('*') if p.is_file()})

    def test_foreign_malformed_attempts_remain_diagnostic_without_aborting_target(self):
        source = {"id": "own", "name": "Own", "manual_routes": [{"url": "https://fixture.invalid/jobs", "method": "isolated_browser"}]}
        observed = {"target_id": "own", "source_url": "https://fixture.invalid/jobs", "transport_status": "blocked", "evidence": "Exact public page blocked"}
        foreign = [{"target_id": "foreign", "url": "not a URL", "method": []},
                   {"target_id": "foreign", "url": observed["source_url"], "method": "unsupported"}, None]
        result = routes.fallback_plan(source, observed, attempted_routes=foreign)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual([r["url"] for r in result["next_routes"]], [observed["source_url"]])
        self.assertEqual([r["attempt"] for r in result["ignored_attempts"]], foreign)
        for method in (None, [], "unsupported"):
            with self.assertRaises(ValueError):
                routes.fallback_plan(source, observed, attempted_routes=[{"url": observed["source_url"], "method": method}])

    def binding_observation(self, complete=True):
        return {"source_id": "arc", "source_url": "https://arc.dev/en-il/remote-jobs",
                "method": "public_page", "transport_status": "success",
                "content_kind": "opportunity_list", "observed_count": 2,
                "scope_complete": complete, "evidence": "Two Arc role cards in this selected scope"}

    def test_target_binding_precedes_complete_partial_and_attempt_handling(self):
        arc = routes.resolve_source(self.catalog, "Arc")
        employer = next(row for row in self.catalog["employer_fallbacks"] if row["id"] == "codevalue")
        expected = employer["manual_routes"]
        for complete in (True, False):
            observation = self.binding_observation(complete)
            for explicit in (True, False):
                with self.subTest(complete=complete, explicit=explicit):
                    candidate = copy.deepcopy(observation)
                    if not explicit:
                        candidate.pop("source_id")
                    candidate["attempted_routes"] = [{"url": row["url"], "method": row["method"]} for row in expected]
                    candidate["resolved_url"] = expected[0]["url"]
                    result = routes.fallback_plan(employer, candidate, [row["url"] for row in expected])
                    self.assertEqual(result["status"], "not_attempted")
                    self.assertEqual([{k: v for k, v in route.items() if k != "applicability_check"} for route in result["next_routes"]], expected[:3])
                    self.assertFalse(result["binding"]["bound"])
            own = routes.fallback_plan(arc, observation)
            self.assertEqual(own["status"], "checked" if complete else "partial")
            self.assertEqual(own["next_routes"], [])

    def test_cli_mixed_selection_has_target_specific_coverage_and_own_observations(self):
        path = self.work / "coverage.json"
        args = [sys.executable, "-X", "utf8", "-B", str(Path(routes.__file__)), str(self.work), "--shared-root", str(self.root),
                "--source", "Arc", "--employer", "CodeValue", "--observation", str(path)]
        for complete in (True, False):
            observation = self.binding_observation(complete)
            observation.pop("source_id")  # Reproduce exact legacy CLI input too.
            path.write_text(json.dumps(observation), encoding="utf-8")
            process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(set(result["coverage"]), {"arc", "codevalue"})
            self.assertEqual(result["coverage"]["codevalue"]["status"], "not_attempted")
            self.assertTrue(result["fallbacks"]["codevalue"]["next_routes"])
            self.assertEqual(result["coverage"]["arc"]["status"], "checked" if complete else "partial")
        own = {**self.binding_observation(), "employer": "CodeValue", "source_url": "https://www.codevalue.com/career"}
        own.pop("source_id")
        path.write_text(json.dumps({"observations": [self.binding_observation(), own]}), encoding="utf-8")
        process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["coverage"]["codevalue"]["status"], "checked")
        self.assertEqual(result["fallbacks"]["codevalue"]["next_routes"], [])
        # Two scopes for one target must not be silently selected or called whole-board coverage.
        path.write_text(json.dumps({"observations": [self.binding_observation(), self.binding_observation(False)]}), encoding="utf-8")
        process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("Multiple observations for target arc", process.stderr)

    def test_binding_aliases_exact_navigation_and_identity_conflicts(self):
        source = routes.resolve_source(self.catalog, "Arc")
        observation = {**self.binding_observation(), "source_id": "CodementorX"}
        self.assertEqual(routes.fallback_plan(source, observation)["status"], "checked")
        detail = "https://arc.dev/remote-jobs/details/exact-fixture"
        linked = {**observation, "source_url": detail, "content_kind": "opportunity_detail",
                  "navigation": {"from_url": observation["source_url"], "to_url": detail, "evidence": "Observed exact role link from Arc list"}}
        self.assertEqual(routes.fallback_plan(source, linked)["status"], "checked")
        for change in ({"source_id": "unknown"}, {"employer": "CodeValue"}, {"source_url": "https://arc.dev/unrelated"}, {"evidence": " "}, {"source_id": []}):
            with self.subTest(change=change):
                result = routes.fallback_plan(source, {**observation, **change})
                self.assertEqual(result["status"], "not_attempted")
                self.assertTrue(result["next_routes"])
        bad = copy.deepcopy(linked); bad["navigation"]["to_url"] = "https://arc.dev/other"
        self.assertEqual(routes.fallback_plan(source, bad)["status"], "not_attempted")

    def test_binding_never_uses_hostname_or_drops_functional_queries(self):
        base = "https://jobs.ashbyhq.com/fixture"
        source = {"id": "one", "name": "One", "manual_routes": [{"url": base+"?embed=js", "method": "isolated_browser"}]}
        observation = {**self.binding_observation(), "source_id": "one", "source_url": base}
        self.assertEqual(routes.fallback_plan(source, observation)["status"], "not_attempted")
        observation["source_url"] = base + "?embed=js&utm_source=fixture"
        self.assertEqual(routes.fallback_plan(source, observation)["status"], "checked")
        shared = {**source, "id": "two", "name": "Two"}
        self.assertEqual(routes.fallback_plan(source, observation, targets=[source, shared])["status"], "not_attempted")
        shared = {**shared, "name": "One", "manual_routes": [{"url": "https://other.invalid/jobs", "method": "public_page"}]}
        self.assertEqual(routes.fallback_plan(source, {**observation, "source_id": "One"}, targets=[source, shared])["status"], "not_attempted")
        observation["source_url"] = "https://jobs.ashbyhq.com/other?embed=js"
        self.assertEqual(routes.fallback_plan(source, observation)["status"], "not_attempted")

    def test_foreign_attempt_identity_and_redirect_do_not_consume_own_routes(self):
        source = routes.resolve_source(self.catalog, "Arc")
        observation = {**self.binding_observation(), "transport_status": "blocked"}
        browser = {"source_id": "CodeValue", "url": observation["source_url"], "method": "isolated_browser"}
        plan = routes.fallback_plan(source, observation, profile={"configured": True, "eligible_countries": ["IL"]}, attempted_routes=[browser, {"url": "https://unrelated.invalid/list", "resolved_url": observation["source_url"], "method": "isolated_browser"}])
        self.assertIn((observation["source_url"], "isolated_browser"), [(r["url"], r["method"]) for r in plan["next_routes"]])
        self.assertEqual(len(plan["ignored_attempts"]), 2)
        own = {"url": observation["source_url"], "resolved_url": source["manual_routes"][-1]["url"], "method": "isolated_browser"}
        plan = routes.fallback_plan(source, observation, profile={"configured": True, "eligible_countries": ["IL"]}, attempted_routes=[own])
        self.assertNotIn((observation["source_url"], "isolated_browser"), [(r["url"], r["method"]) for r in plan["next_routes"]])
        self.assertEqual(plan["ignored_attempts"], [])

    def test_original_catalog_website_only_source_binds_exact_anchor_or_navigation(self):
        source = routes.resolve_source(self.catalog, "Upwork")
        self.assertFalse(source.get("manual_routes"))
        observed = {**self.binding_observation(), "source_id": "upwork", "source_url": source["website"]}
        self.assertEqual(routes.fallback_plan(source, observed)["status"], "checked")
        listing = source["website"].rstrip("/") + "/jobs/exact-fixture"
        paired = {**observed, "source_url": listing,
                  "navigation": {"from_url": source["website"], "to_url": listing, "evidence": "Observed this exact public listing from the catalog anchor"}}
        self.assertEqual(routes.fallback_plan(source, paired)["status"], "checked")
        for change in ({"source_id": "arc"}, {"navigation": {}}, {"source_url": "https://unrelated.invalid/jobs/exact-fixture"}):
            self.assertEqual(routes.fallback_plan(source, {**paired, **change})["status"], "not_attempted")

    def test_partial_continuation_needs_real_count_and_nonblank_scope_evidence(self):
        source = {"manual_routes": [{"url": "https://fixture.invalid/jobs", "method": "isolated_browser"}]}
        working = {"transport_status": "success", "content_kind": "opportunity_list", "observed_count": 2,
                   "source_url": "https://fixture.invalid/jobs", "evidence": "Two real cards and another page", "scope_complete": False}
        self.assertEqual(routes.fallback_plan(source, working)["next_action"], "continue_selected_route_coverage")
        for change in ({"observed_count": True}, {"observed_count": "2"}, {"observed_count": -1}, {"observed_count": None},
                       {"source_url": " "}, {"evidence": " "}, {"content_kind": "js_shell"}):
            self.assertNotIn("next_action", routes.fallback_plan(source, {**working, **change}))
        for attempt in ({"url": working["source_url"]}, {"url": working["source_url"], "method": []}):
            with self.assertRaises(ValueError):
                routes.fallback_plan(source, {**working, "transport_status": "blocked"}, attempted_routes=[attempt])

    def test_scoped_method_alternatives_preserve_positional_profile_and_recompute(self):
        matching = {"configured": True, "eligible_countries": ["IL"], "search_brief": {"required_stack": ["dotnet"]}}
        other = {"configured": True, "eligible_countries": ["CA"], "search_brief": {"required_stack": ["python"]}}
        source = routes.select_sources(self.catalog, ["arc"], matching)[0]
        scoped = "https://arc.dev/en-il/remote-jobs"
        allowed = routes.fallback_plan(source, {"transport_status": "blocked"}, [scoped], matching)
        self.assertIn((scoped, "isolated_browser"), [(r["url"], r["method"]) for r in allowed["next_routes"]])
        for profile in (other, {}):
            blocked = routes.fallback_plan(source, {"transport_status": "blocked"}, [], profile)
            self.assertNotIn(scoped, [r["url"] for r in blocked["next_routes"]])
            self.assertEqual(len(blocked["unrecommended_scoped_routes"]), 2)

    def test_supplement_preserves_seven_employer_routes_and_historical_limits(self):
        rows = {r["id"]: r for r in self.catalog["employer_fallbacks"]}
        self.assertEqual(len(rows), 7)
        self.assertTrue({"ness", "the_trade_desk", "candex"} <= rows.keys())
        candex = rows["candex"]
        self.assertEqual((candex["manual_routes"][0]["url"], candex["manual_routes"][0]["method"]),
                         ("https://jobs.ashbyhq.com/candex?embed=js", "isolated_browser"))
        self.assertTrue(candex["research_history"])
        self.assertEqual(candex["research_evidence"]["named_role_links"], 5)
        self.assertEqual(candex["research_evidence"]["talent_pool_rows"], 1)
        for row in rows.values():
            for route in row["manual_routes"]:
                self.assertIn(route["method"], routes.ROUTE_METHODS)

    def test_invitation_and_hn_required_identity_fields_cannot_be_whitespace(self):
        project = {"type": "project", "response_mode": "client_invitation", "id": "project:1", "url": "https://fixture.invalid/1",
                   "company": "Fixture Client", "description": "A concrete paid project"}
        self.assertTrue(routes.opportunity_candidate(project))
        for field in ("id", "url", "company", "description"):
            self.assertFalse(routes.opportunity_candidate({**project, field: " "}))
        alias = {"id": "ats:1", "url": "https://fixture.invalid/1", "employer": "Fixture", "source_job_id": "req1", "identity_evidence": "Exact linked requisition"}
        item = {"id": 10, "time": 1700000000, "type": "comment", "parent": 1}
        for field in alias:
            with self.assertRaises(ValueError):
                routes.hn_candidate(item, 1, {**alias, field: " "})
        with self.assertRaises(ValueError):
            routes.hn_candidate(item, 1, {**alias, "employer_or_client": "Different client"})

    def test_hn_alias_connects_reported_and_suppressed_employer_requisition_after_reload(self):
        item = {"id": 8801, "parent": 1, "time": 1700000000, "type": "comment", "text": "Employer's exact opening"}
        alias = {"id": "employer:public-A", "url": "https://employer.invalid/openings/A", "employer": "Fixture Employer", "source_job_id": "REQ-42", "identity_evidence": "Exact employer requisition REQ-42 linked in this hiring comment"}
        candidate = routes.hn_candidate(item, 1, alias)
        prior = {"id": "supplier:old-B", "url": "https://supplier.invalid/jobs/B", "company": "Fixture Employer", "source_job_id": "REQ-42", "reported_at": "2026-01-01T12:00:00Z"}
        found, applied = {"opportunities": [prior]}, {"records": []}
        self.assertEqual(records.history_decision(candidate, found, applied)["state"], "previously_reported")
        applied["records"] = [{**prior, "suppress_from_new_results": True}]
        records.save(self.work / "data/jobs.json", {"opportunities": [candidate]})
        records.save(self.work / "data/applied_jobs.json", applied)
        saved_found, saved_applied = records.read_store(self.work)
        self.assertEqual(records.history_decision(saved_found["opportunities"][0], saved_found, saved_applied)["state"], "suppressed")
        self.assertEqual(candidate["source_aliases"][0]["employer"], alias["employer"])
        self.assertEqual(candidate["source_aliases"][0]["identity_evidence"], alias["identity_evidence"])
        for empty in (None, "", " "):
            normalized = routes.hn_candidate(item, 1, {**alias, "company": empty, "employer_or_client": empty})
            self.assertEqual(records.history_decision(normalized, found, {"records": []})["state"], "previously_reported")
        for wrong in ({"company": "Unrelated Employer"}, {"source_url": "https://unrelated.invalid/jobs/999"}):
            with self.assertRaises(ValueError):
                routes.hn_candidate(item, 1, {**alias, **wrong})
        other = {**prior, "source_job_id": "REQ-99"}
        self.assertEqual(records.history_decision(candidate, {"opportunities": [other]}, {"records": []})["state"], "new")

    def test_fallback_attempts_are_method_specific_and_legacy_urls_do_not_hide_browser(self):
        url = "https://jobs.fixture.invalid/team"
        source = {"manual_routes": [{"url": url, "method": "public_page"}, {"url": url, "method": "isolated_browser"}, {"url": "https://employer.invalid/careers", "method": "public_page"}]}
        failed = {"transport_status": "blocked", "source_url": url, "method": "public_page", "evidence": "Extractor403"}
        plan = routes.fallback_plan(source, failed, [url])
        self.assertIn((url, "isolated_browser"), [(r["url"], r["method"]) for r in plan["next_routes"]])
        self.assertNotIn((url, "public_page"), [(r["url"], r["method"]) for r in plan["next_routes"]])
        both = routes.fallback_plan(source, failed, attempted_routes=[{"url": url, "method": "public_page"}, {"url": url, "method": "isolated_browser"}])
        self.assertNotIn(url, [r["url"] for r in both["next_routes"]])
        no_legacy = routes.fallback_plan(source, failed)
        self.assertNotIn((url, "public_page"), [(r["url"], r["method"]) for r in no_legacy["next_routes"]])
        working = {**failed, "transport_status": "success", "content_kind": "opportunity_list", "observed_count": 10, "scope_complete": False, "evidence": "Ten actual cards and next-page link"}
        continuation = routes.fallback_plan(source, working)
        self.assertEqual(continuation["next_routes"], [])
        self.assertEqual(continuation["next_action"], "continue_selected_route_coverage")
        self.assertEqual(routes.fallback_plan(source, {**working, "scope_complete": True})["next_routes"], [])

    def test_functional_query_and_redirect_attempts_remain_distinct_without_loops(self):
        root = "https://jobs.ashbyhq.com/fixture"
        embed = root + "?embed=js"
        corporate = "https://www.fixture.invalid/site/careers/"
        source = {"website": "https://www.fixture.invalid/careers", "manual_routes": [{"url": root, "method": "isolated_browser"}, {"url": embed, "method": "isolated_browser"}, {"url": corporate, "method": "public_page"}]}
        blocked = {"transport_status": "failed", "source_url": root, "method": "isolated_browser", "evidence": "Page not found"}
        plan = routes.fallback_plan(source, blocked, attempted_routes=[{"url": "https://www.fixture.invalid/careers", "resolved_url": corporate, "method": "public_page"}])
        self.assertEqual([(r["url"], r["method"]) for r in plan["next_routes"]], [(embed, "isolated_browser")])
        self.assertNotEqual(routes.route_attempt_key(corporate+"?ashby_jid=one"), routes.route_attempt_key(corporate+"?ashby_jid=two"))
        self.assertEqual(routes.route_attempt_key(embed+"&utm_source=tracker"), routes.route_attempt_key(embed))
        done = routes.fallback_plan(source, blocked, attempted_routes=[{"url": corporate, "method": "public_page"}, {"url": embed, "method": "isolated_browser"}])
        self.assertTrue(done["exhausted"])
        self.assertEqual(done["next_routes"], [])

    def test_scoped_historical_routes_require_matching_explicit_preferences(self):
        matching = copy.deepcopy(self.profile)
        matching["eligible_countries"] = ["IL"]
        matching["search_brief"]["required_stack"] = ["dotnet"]
        other = copy.deepcopy(matching)
        other["eligible_countries"] = ["CA"]
        other["search_brief"]["required_stack"] = ["python"]
        sources = [routes.resolve_source(self.catalog, name) for name in ("arc", "scalable_path")]
        scoped_urls = {source["manual_routes"][0]["url"] for source in sources}
        before = copy.deepcopy(sources)
        for profile, expected in ((matching, "applicable"), (other, "inapplicable"), ({}, "unknown"), ({**matching, "configured": False}, "unknown")):
            selected = routes.select_sources(self.catalog, ["arc", "scalable_path"], profile)
            for source in selected:
                scoped = source["manual_routes"][0]
                self.assertEqual(scoped["applicability_check"]["status"], expected)
                self.assertFalse(scoped["applicability_check"]["qualification_verified"])
                recommended = {route["url"] for route in source["recommended_routes"]}
                self.assertEqual(scoped["url"] in recommended, expected == "applicable")
                fallback = routes.fallback_plan(source, {"transport_status": "blocked"}, profile=profile)
                self.assertEqual(scoped["url"] in {route["url"] for route in fallback["next_routes"]}, expected == "applicable")
                self.assertFalse(fallback["executes_network"])
        self.assertEqual(sources, before)
        self.assertEqual(scoped_urls, {"https://arc.dev/en-il/remote-jobs", "https://www.scalablepath.com/dot-net/jobs"})
        records.save(self.work / "profile.json", other)
        inputs = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        process = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(routes.__file__)), str(self.work), "--source", "Arc", "--source", "Scalable Path"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertFalse(result["executes_network"])
        self.assertTrue(all(source["manual_routes"][0]["applicability_check"]["status"] == "inapplicable" for source in result["sources"]))
        self.assertEqual(inputs, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})

    def test_private_workdir_resolves_public_catalog_for_planning_and_outcomes(self):
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        catalog = routes.load_catalog(self.work)
        self.assertEqual(len(catalog["sources"]), 28)
        self.assertEqual(routes.resolve_source(catalog, "CodementorX")["id"], "arc")
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})
        records.save(self.work / "data/jobs.json", {"opportunities": [{"id": "synthetic:1", "source": "CodementorX"}]})
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        inputs = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        report = outcomes.write_report(self.work, "reports/outcomes.md")
        self.assertEqual(set(report["by_source"]), {"arc"})
        self.assertTrue(all(p.read_bytes() == raw for p, raw in inputs.items()))
        self.assertFalse((self.work / "sources/manual-discovery.json").exists())

    def test_fallback_unique_normalized_routes_and_blank_evidence(self):
        source = {"manual_routes": [{"url": value} for value in ["https://fixture.invalid/a/", "https://fixture.invalid/a", "https://www.fixture.invalid/a", "https://fixture.invalid/b", "https://fixture.invalid/c", "https://fixture.invalid/d"]]}
        blocked = {"transport_status": "blocked", "source_url": "https://fixture.invalid/a", "evidence": "Recorded exact route failure"}
        plan = routes.fallback_plan(source, blocked)
        self.assertEqual(len(plan["next_routes"]), 3)
        self.assertEqual(len({routes.source_key(r["url"]) for r in plan["next_routes"]}), 3)
        plan = routes.fallback_plan(source, blocked, ["https://fixture.invalid/a"])
        self.assertNotIn("fixture.invalid/a", {routes.source_key(r["url"]) for r in plan["next_routes"]})
        complete = {"transport_status": "success", "content_kind": "opportunity_list", "source_url": "https://fixture.invalid/jobs", "evidence": "Bounded list inspected", "observed_count": 0, "scope_complete": True, "explicit_empty_evidence": "No entries"}
        for field in ("source_url", "evidence", "explicit_empty_evidence"):
            self.assertEqual(routes.coverage_observation({**complete, field: "  "})["status"], "partial")
        with self.assertRaises(ValueError):
            routes.hn_candidate({"id": 2, "parent": 1, "time": 1700000000, "type": "comment"}, 1, {"id": "ats:3", "url": "https://fixture.invalid/3", "employer": "Fixture", "source_job_id": "3", "identity_evidence": " "})

    def setUp(self):
        super().setUp()
        # Catalog is public source metadata only; canonical personal records are not read.
        self.root = SKILL.parents[1]
        if not (self.root / "sources/manual-discovery.json").exists():
            self.root = Path(json.loads((SKILL / "workspace.json").read_text("utf-8"))["workspace"])
        self.catalog = routes.load_catalog(self.root)

    def test_current_catalog_retains_base_and_selects_five_without_duplicate_guru(self):
        expected = {'freelancer','freelancehunt','upwork','fl_ru','codeur','himalayas','remote_ok','we_work_remotely','jobicy','remotive','peopleperhour','workana','freelancermap','xplace','fiverr','guru','malt','lemon_io','proxify','yunojuno','toptal','contra','braintrust'}
        self.assertEqual(set(self.catalog["sources"]), expected | {'arc','hn','scalable_path','x_team','gun_io'})
        guru = routes.resolve_source(self.catalog, "Guru")
        self.assertIn("403", guru["evidence"]["observation"])
        self.assertEqual(guru["discovery_method"], "manual_public_project_search_and_quote")
        self.assertEqual(guru["quote_workflow"]["api_access"], "unverified")
        self.assertEqual(len(routes.select_sources(self.catalog, ["guru", "Guru", "https://www.guru.com/"])), 1)

    def test_lifecycle_aliases_do_not_collapse_ownership_or_opportunities(self):
        self.assertEqual(len(routes.select_sources(self.catalog, ["arc", "CodementorX", "https://codementorx.com/"])), 1)
        with self.assertRaises(ValueError):
            routes.resolve_source(self.catalog, "Codementor")
        self.assertEqual(routes.resolve_source(self.catalog, "AngelList Talent")["id"], "wellfound_reference")
        with self.assertRaises(ValueError):
            routes.resolve_source(self.catalog, "AngelList Venture")
        self.assertNotEqual(routes.resolve_source(self.catalog, "Adeva")["id"], routes.resolve_source(self.catalog, "Toptal")["id"])
        self.assertFalse(routes.resolve_source(self.catalog, "Worksome")["selected_for_search"])
        rows = [{"id": "arc:one", "company": "Same", "title": "Same"}, {"id": "arc:two", "company": "Same", "title": "Same"}]
        self.assertEqual(len(records.identity_groups(rows)), 2)

    def test_ambiguous_alias_rejected_without_changing_files(self):
        (self.work / "sources").mkdir()
        for name in ("opportunity-sources.json", "manual-discovery.json"):
            (self.work / "sources" / name).write_bytes((self.root / "sources" / name).read_bytes())
        path = self.work / "sources/opportunity-sources.json"
        value = json.loads(path.read_text("utf-8"))
        value["sources"][0]["aliases"] = ["CodementorX"]
        path.write_text(json.dumps(value), encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            routes.load_catalog(self.work, shared=self.work)
        self.assertEqual(before, path.read_bytes())

    def test_admission_and_services_never_become_opportunities(self):
        item = {"opportunity_id": "fake", "listing_url": "https://fixture.invalid/join", "employer_or_client": "Network", "description_evidence": "Join us"}
        for mode in ("network_admission", "generic_agency_screening", "client_invitation"):
            self.assertFalse(routes.opportunity_candidate({**item, "record_kind": "opportunity", "response_mode": mode}))
        self.assertFalse(routes.opportunity_candidate({**item, "record_kind": "source_access", "response_mode": "project_proposal"}))
        self.assertTrue(routes.opportunity_candidate({**item, "record_kind": "opportunity", "response_mode": "project_proposal"}))
        self.assertTrue(routes.opportunity_candidate({**item, "record_kind": "opportunity", "response_mode": "agency_screening"}))
        self.assertFalse(routes.opportunity_candidate({**item, "record_kind": "source_access", "response_mode": "agency_screening"}))
        # Discovery candidacy deliberately does not claim fit, freshness or eligibility.

    def test_failure_shell_and_category_empty_are_not_complete_zero(self):
        base = {"transport_status": "success", "source_url": "https://fixture.invalid/jobs", "evidence": "Total lines: 195", "observed_count": 0, "scope_complete": True}
        for kind in ("line_count", "js_shell", "blank_frame", "login", "home"):
            self.assertEqual(routes.coverage_observation({**base, "content_kind": kind})["status"], "partial")
        self.assertEqual(routes.coverage_observation({**base, "transport_status": "blocked", "content_kind": "opportunity_list"})["status"], "blocked")
        self.assertEqual(routes.coverage_observation({**base, "content_kind": "opportunity_list"})["status"], "partial")
        mixed = {**base, "content_kind": "opportunity_list", "observed_count": 17, "explicit_empty_evidence": "Other category is empty"}
        self.assertEqual(routes.coverage_observation(mixed)["status"], "checked")
        empty = {**base, "content_kind": "opportunity_list", "explicit_empty_evidence": "No .NET positions", "evidence": "Completed exact .NET category, no pagination"}
        self.assertEqual(routes.coverage_observation(empty)["status"], "checked_empty")
        scalable = routes.resolve_source(self.catalog, "scalable_path")
        self.assertEqual(routes.fallback_plan(scalable, {**empty, "source_id": "scalable_path", "source_url": scalable["manual_routes"][0]["url"]})["next_routes"], [])

    def test_documented_fallbacks_bounded_and_cli_does_not_execute(self):
        source = routes.resolve_source(self.catalog, "guru")
        failed = {"transport_status": "blocked", "source_url": source["manual_routes"][0]["url"], "evidence": "Extractor403"}
        plan = routes.fallback_plan(source, failed, [failed["source_url"]])
        self.assertEqual(plan["max_attempts_per_route"], 1)
        self.assertNotIn((failed["source_url"], "public_page"), [(row["url"], row["method"]) for row in plan["next_routes"]])
        self.assertFalse(plan["executes_network"])
        process = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(routes.__file__)), str(self.root), "--source", "CodementorX", "--source", "Arc", "--employer", "CodeValue"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        output = json.loads(process.stdout)
        self.assertEqual(output["count"], 1)
        self.assertEqual(output["employer_fallbacks"][0]["manual_routes"][0]["url"], "https://www.codevalue.com/career")
        self.assertFalse(output["executes_network"])

    def test_hn_item_dates_dead_items_and_separate_job_stories(self):
        item = {"id": 42, "parent": 1, "time": 1700000000, "type": "comment", "text": "Exact hiring post", "url": "https://employer.invalid/jobs/7"}
        alias = {"id": "ats:7", "source_job_id": "7", "url": item["url"], "employer": "Fixture", "identity_evidence": "Comment explicitly links requisition7"}
        row = routes.hn_candidate(item, 1, alias)
        self.assertEqual(row["id"], "hn:42")
        self.assertEqual(row["thread_id"], 1)
        self.assertEqual(records.timestamp(row["publication_events"][0]["at"]).timestamp(), item["time"])
        self.assertEqual(row["source_aliases"], [{**alias, "company": alias["employer"]}])
        self.assertFalse(row["description_complete"])
        self.assertIsNone(row["refresh_evidence"])
        self.assertIsNone(routes.hn_candidate(item, 999))
        for flag in ("dead", "deleted"):
            self.assertIsNone(routes.hn_candidate({**item, flag: True}, 1))
        story = routes.hn_candidate({**item, "type": "job"}, 1)
        self.assertIsNone(story["thread_id"])
        self.assertEqual(story["publication_events"][0]["scope"], "job_story")
        with self.assertRaises(ValueError):
            routes.hn_candidate(item, 1, {"id": "ats:7"})

    def test_explicit_manual_saved_window_and_minimum_do_not_change_profile(self):
        now = dt.datetime.now(dt.timezone.utc)
        start = now - dt.timedelta(hours=60)
        saved = {"run_type": "manual", "execution_context": "manual", "requested_minimum": 7, "result_cap": None, "window_start": start.isoformat(), "window_end": now.isoformat(), "source_windows": {k: {"hours": 60, "window_start": start.isoformat(), "window_end": now.isoformat()} for k in ("other", "employer_registry", "techmap")}}
        before = copy.deepcopy(self.profile)
        brief = qualification.search_brief(self.profile, now + dt.timedelta(days=1), saved)
        review = {"publication": {"kind": "original", "at": (now-dt.timedelta(hours=48)).isoformat(), "source_url": "https://fixture.invalid/job/1", "evidence": "Exact source publication"}}
        self.assertTrue(qualification.freshness(review, brief, {}, now)["passed"])
        self.assertEqual(brief["source_windows"], saved["source_windows"])
        self.assertEqual(brief["requested_minimum"], 7)
        self.assertEqual(self.profile, before)
        collector = qualification.search_brief(self.profile, now, saved, execution_context="collector")
        self.assertFalse(qualification.freshness(review, collector, {}, now)["passed"])


class DraftQualityTests(OfflineCase):

    def test_canonical_upload_event_reused_unchanged_in_draft_review(self):
        import packets
        now = dt.datetime.now(dt.timezone.utc)
        event = {"status": "uploaded", "opportunity_id": "job:1", "sha256": "hash", "at": now.isoformat(), "evidence": "Synthetic exact-file upload observation; no external upload", "authorization": "Fixture-only authorization"}
        packets.record_submission_event(self.work, {"id": "job:1"}, event)
        _, applied = records.read_store(self.work)
        saved = applied["records"][0]["submission_events"][0]
        self.assertEqual(saved, event)
        draft = self.draft(text="I have attached my CV.")
        draft.update(attachment_evidence=saved, attachment_intended=True, attachment_quality={"content_reviewed": True, "render_reviewed": True, "role_language_confirmed": True, "no_unresolved_material_facts": True, "evidence": "Fixture exact-file content/layout review", "version_id": "current", "sha256": "hash"})
        cv = {"current_sha256": "hash", "file_status": "hash_matches", "version_id": "current", "ready_to_attach": True, "content_reviewed": True, "unresolved_facts": [], "content_review": {"status": "reviewed", "sha256": "hash", "evidence": "Synthetic reviewed content"}}
        result = drafts.prepare_draft(draft, "job:1", cv, now=now)
        self.assertTrue(result["review"]["ready_for_use"], result)
        self.assertTrue(result["attachment_check"]["observed_uploaded"])
        self.assertEqual(result["state"], "not_sent")
        self.assertFalse(records.application_evidence(applied["records"][0])["ever_applied"])
        for wrong in ({"opportunity_id": "job:other"}, {"sha256": "wrong"}, {"at": (now+dt.timedelta(days=1)).isoformat()}, {"status": "prepared"}, {"authorization": ""}, {"authorization": " "}, {"evidence": " "}, {"at": now.replace(tzinfo=None).isoformat()}):
            with self.subTest(wrong=wrong):
                altered = copy.deepcopy(draft);altered["attachment_evidence"].update(wrong)
                self.assertFalse(drafts.prepare_draft(altered, "job:1", cv, now=now)["review"]["ready_for_use"])

    def test_blank_evidence_and_contradictory_or_stale_attachment_quality(self):
        for change in ({"recipient_evidence": " "}, {"content_evidence": {k: "\t" for k in drafts.MODES["employer"]["parts"]}}, {"claim_review": {**self.draft()["claim_review"], "evidence": " "}}):
            self.assertFalse(drafts.prepare_draft({**self.draft(), **change}, "job:1")["review"]["ready_for_use"])
        cv = {"version_id": "current", "current_sha256": "hash", "file_status": "hash_matches", "ready_to_attach": True, "content_reviewed": True, "unresolved_facts": [], "content_review": {"status": "reviewed", "sha256": "hash", "evidence": "Actual synthetic content review"}}
        quality = {"version_id": "current", "sha256": "hash", "evidence": "Attributed exact-version quality review", **{k: True for k in ("content_reviewed", "render_reviewed", "role_language_confirmed", "no_unresolved_material_facts")}}
        draft = {**self.draft(), "attachment_intended": True, "attachment_quality": quality}
        self.assertTrue(drafts.prepare_draft(draft, "job:1", cv)["review"]["ready_for_use"])
        for change in ({"ready_to_attach": False}, {"content_reviewed": False}, {"unresolved_facts": ["Unresolved synthetic date"]}, {"file_status": "changed_since_manifest"}, {"content_review": {"status": "reviewed", "sha256": "old", "evidence": "Earlier file"}}):
            self.assertFalse(drafts.prepare_draft(draft, "job:1", {**cv, **change})["review"]["ready_for_use"])
        for change in ({"sha256": "old"}, {"version_id": "old"}, {"evidence": " "}):
            self.assertFalse(drafts.prepare_draft({**draft, "attachment_quality": {**quality, **change}}, "job:1", cv)["review"]["ready_for_use"])

    def test_standalone_private_outputs_preserve_inputs_without_a_profile(self):
        (self.work / "profile.json").unlink()
        request = self.work / "request.json"
        records.save(request, {"draft": self.draft("network")})
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        for output in (request, "profile.json", "profile-evidence.json", "cv-manifest.json", "data/jobs.json", "reviews.json", "../escaped.json", SKILL.parents[1] / "templates/profile.template.json"):
            with self.assertRaises(ValueError):
                drafts.write_draft(self.work, request, output)
            self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})
        result = drafts.write_draft(self.work, request, "drafts/network.json")
        self.assertTrue(result["review"]["ready_for_use"])
        self.assertFalse((self.work / "profile.json").exists())

    def draft(self, mode="employer", text="Supported wording for the observed recipient."):
        return {"recipient_type": mode, "stage": drafts.MODES[mode]["stage"], "text": text, "recipient_evidence": "Observed exact recipient/channel", "content_evidence": {key: "Reviewed relevant source fact" for key in drafts.MODES[mode]["parts"]}, "claim_review": {"experience_supported": True, "terms_supported_or_omitted": True, "language_confirmed": True, "submission_wording_checked": True, "evidence": "Reviewed supported experience, omitted unconfirmed terms and observed English field"}}

    def test_four_recipients_keep_distinct_stage_and_unsent_network_not_opportunity(self):
        for mode in drafts.MODES:
            result = drafts.prepare_draft(self.draft(mode), None if mode == "network" else "job:1")
            self.assertTrue(result["review"]["ready_for_use"], result)
            self.assertEqual(result["stage"], drafts.MODES[mode]["stage"])
            self.assertEqual(result["state"], "not_sent")
            self.assertFalse(result["review"]["external_action_authorized"])
            if mode == "network":
                self.assertFalse(result["counts_as_opportunity"])
        with self.assertRaises(ValueError):
            drafts.prepare_draft({**self.draft("network"), "stage": "project_proposal"})

    def test_attachment_claim_requires_exact_upload_and_file_quality(self):
        now = dt.datetime.now(dt.timezone.utc)
        cv = {"version_id": "synthetic-version", "current_sha256": "hash", "file_status": "hash_matches", "ready_to_attach": True, "content_reviewed": True, "unresolved_facts": [], "content_review": {"status": "reviewed", "sha256": "hash", "evidence": "Reviewed synthetic version"}}
        draft = self.draft(text="I have attached my CV.")
        self.assertFalse(drafts.prepare_draft(draft, "job:1", cv)["review"]["ready_for_use"])
        draft["attachment_evidence"] = {"opportunity_id": "job:1", "sha256": "hash", "status": "uploaded_observed", "at": now.isoformat(), "evidence": "Exact file visible in authorized upload control", "authorization": "Synthetic fixture authorization"}
        self.assertTrue(drafts.prepare_draft(draft, "job:1", cv, now=now)["review"]["ready_for_use"])
        for change in ({"opportunity_id": "other"}, {"sha256": "other"}, {"status": "prepared"}, {"at": (now+dt.timedelta(days=1)).isoformat()}):
            bad = copy.deepcopy(draft);bad["attachment_evidence"].update(change)
            self.assertFalse(drafts.prepare_draft(bad, "job:1", cv, now=now)["review"]["ready_for_use"])
        draft["attachment_intended"] = True
        self.assertFalse(drafts.prepare_draft(draft, "job:1", cv, now=now)["review"]["ready_for_use"])
        draft["attachment_quality"] = {k: True for k in ("content_reviewed", "render_reviewed", "role_language_confirmed", "no_unresolved_material_facts")}
        draft["attachment_quality"].update(evidence="Observed content and rendered pages of exact file", version_id="synthetic-version", sha256="hash")
        self.assertTrue(drafts.prepare_draft(draft, "job:1", cv, now=now)["review"]["ready_for_use"])

    def test_placeholders_submission_claims_unknown_terms_and_field_limits_not_ready(self):
        for text in ("Hello [CLIENT]", "Hello {{CLIENT}}", "I submitted my application", "הגשתי מועמדות למשרה", "מצורפים קורות חיים"):
            self.assertFalse(drafts.prepare_draft(self.draft(text=text), "job:1")["review"]["ready_for_use"], text)
        draft = self.draft();draft["claim_review"]["terms_supported_or_omitted"] = False
        self.assertFalse(drafts.prepare_draft(draft, "job:1")["review"]["ready_for_use"])
        draft = self.draft();draft["observed_character_limit"] = 3
        self.assertFalse(drafts.prepare_draft(draft, "job:1")["review"]["ready_for_use"])
        self.assertTrue(drafts.prepare_draft(self.draft(text="Evidence: [public sample](https://fixture.invalid/sample)"), "job:1")["review"]["ready_for_use"])

    def test_portfolio_handoff_requires_relevance_contribution_and_disclosure(self):
        sample = {"selected_for": "Integration requirement", "source_url": "https://fixture.invalid/example", "individual_contribution": "Specific integration code", "evidence": "Reviewed public sample", "visibility": "public"}
        result = drafts.prepare_draft(self.draft(), "job:1", portfolio=[sample])
        self.assertTrue(result["portfolio_handoff"][0]["ready_for_draft"])
        self.assertFalse(drafts.prepare_draft(self.draft(), "job:1", portfolio=[{**sample, "visibility": "private"}])["review"]["ready_for_use"])

    def test_local_network_cli_and_maintained_boilerplate_make_no_attachment_claim(self):
        records.save(self.work / "request.json", {"draft": self.draft("network")})
        process = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(drafts.__file__)), str(self.work), "--input", str(self.work / "request.json"), "--output", str(self.work / "network-draft.json")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = records.load(self.work / "network-draft.json")
        self.assertEqual(result["state"], "not_sent")
        self.assertFalse(result["counts_as_opportunity"])
        self.assertFalse((self.work / "data/jobs.json").exists())
        root = SKILL.parents[1]
        content = (root / "skills/workhunt-apply/references/recipient-drafts.md").read_text("utf-8")
        for paragraph in content.split("\n\n"):
            if paragraph.startswith("Hello "):
                self.assertIsNone(drafts.ATTACHMENT_CLAIM.search(paragraph))


class OptionalOutcomeTests(OfflineCase):
    def test_malformed_events_stay_diagnosed_and_do_not_erase_valid_peers(self):
        bad = [None, "not an event", {}, {"event_id": " "}, self.event("bad-kind", []), self.event("bad-currency", "proposal_spend", amount=1, currency="123"), self.event("blank-currency", "proposal_spend", amount=1, currency="   ")]
        report = outcomes.build_report({"opportunities": [{"id": "one", "source": "fixture", "outcome_events": [*bad, self.event("valid-reply", "reply_observed")]}], "search_runs": [{"source_activity": {"unexpected": "collection"}}]}, {"records": []})
        evidence = report["operational_evidence"]
        self.assertEqual(evidence["supported_event_count"], 1)
        self.assertEqual(set(evidence["unresolved_event_ids"]), {"bad-kind", "bad-currency", "blank-currency"})
        self.assertEqual(len(evidence["malformed_events"]), 5)
        self.assertTrue(all("recorded_value" in item and "location" in item for item in evidence["malformed_events"]))
        self.assertEqual(evidence["by_source"]["fixture"]["reply_identities"], 1)
        self.assertEqual(evidence["by_source"]["fixture"]["proposal_spend_by_currency"], {})
        self.assertIsNone(evidence["by_source"]["fixture"]["interview_identities"])

    def event(self, identifier, kind, **fields):
        return {"event_id": identifier, "kind": kind, "source": "fixture", "at": "2026-01-01T12:00:00Z", "evidence": "Supplied observed record", **fields}

    def test_research_or_spending_only_preserves_unknown_outcomes(self):
        for event in (self.event("time", "research_time", seconds=90), self.event("cost", "proposal_spend", amount=5, currency="USD")):
            report = outcomes.build_report({"opportunities": [], "search_runs": [{"source_activity": [event]}]}, {"records": []})
            bucket = report["operational_evidence"]["by_source"]["fixture"]
            self.assertIsNone(bucket["reply_identities"])
            self.assertIsNone(bucket["interview_identities"])
            self.assertIsNone(bucket["paid_engagement_identities"])
            self.assertIn("unknown", outcomes.markdown(report))

    def test_events_deduplicate_identity_and_keep_currency_and_unknowns(self):
        events = [self.event("reply", "reply_observed"), self.event("paid", "paid_engagement_observed"), self.event("cost", "proposal_spend", amount=2, currency="USD")]
        one = {"id": "same", "source": "fixture", "outcome_events": events}
        report = outcomes.build_report({"opportunities": [one, copy.deepcopy(one)], "search_runs": []}, {"records": []})
        bucket = report["operational_evidence"]["by_source"]["fixture"]
        self.assertEqual(report["unique_discovered_identities"], 1)
        self.assertEqual(bucket["reply_identities"], 1)
        self.assertEqual(bucket["paid_engagement_identities"], 1)
        self.assertIsNone(bucket["interview_identities"])
        self.assertEqual(bucket["proposal_spend_by_currency"], {"USD": 2})
        self.assertIsNone(bucket["research_seconds"])

    def test_invalid_future_conflicting_and_wrong_source_events_not_promoted(self):
        events = [self.event("future", "reply_observed", at="2999-01-01T00:00:00Z"), self.event("wrong-source", "reply_observed", source="other"), self.event("negative", "proposal_spend", amount=-1, currency="USD"), self.event("conflict", "research_time", seconds=2), self.event("conflict", "research_time", seconds=9)]
        report = outcomes.build_report({"opportunities": [{"id": "one", "source": "fixture", "outcome_events": events}]}, {"records": []})
        self.assertEqual(report["operational_evidence"]["supported_event_count"], 0)
        self.assertEqual(len(report["operational_evidence"]["unresolved_event_ids"]), 4)

    def test_source_alias_attribution_and_saved_reasons_keep_known_denominator(self):
        catalog = {"alias_index": {"codementorx": "arc", "arc": "arc"}}
        event = self.event("reply", "reply_observed", source="CodementorX")
        row = {"id": "one", "source": "Arc", "status": "excluded", "reason": "Foreign work permit mandatory", "outcome_events": [event]}
        report = outcomes.build_report({"opportunities": [row]}, {"records": []}, source_catalog=catalog)
        self.assertEqual(set(report["by_source"]), {"arc"})
        bucket = report["operational_evidence"]["by_source"]["arc"]
        self.assertEqual(bucket["reply_identities"], 1)
        self.assertEqual(bucket["discovery_denominator"], 1)
        self.assertEqual(bucket["saved_rejections_by_reason"], {"Foreign work permit mandatory": 1})
