from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import sqlite3
import unittest

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.legacy_schemas_v1 import ApplyAmendmentRequest, GateRecommendation
from backend.services.pdf_intake import extract_pdf, parse_notice
from backend.services.provenance import source_gate
from backend.storage import ServiceError
from backend.tests.test_api import APIHarness
from backend.tests.pdf_support import notice_text, pdf_bytes


class APISafetyTests(APIHarness):
    def test_import_never_activates_original_or_amendment(self):
        self.upload(self.original, "ORIGINAL")
        self.upload(self.corrigendum, "CORRIGENDUM")
        state = self.client.get(self.base).json()
        self.assertEqual(state["revision"], 0)
        self.assertEqual(state["active_rules"], [])
        self.assertEqual(state["decisions"][0]["status"], "UNKNOWN")
        self.assertEqual(self.client.get(self.base + "/events").json()["events"], [])

    def test_explicit_human_review_is_mandatory(self):
        original = self.upload(self.original, "ORIGINAL")
        url = self.base + f"/documents/{original['document']['document_id']}/review"
        for body in [dict(expected_workspace_revision=0,reviewed_by="operator",confirm_source_review=False), dict(expected_workspace_revision=0,reviewed_by=" ",confirm_source_review=True), dict(expected_workspace_revision=0,reviewed_by="operator")]:
            self.assertEqual(self.client.post(url, json=body).status_code, 422)
        self.assertEqual(self.client.get(self.base).json()["revision"], 0)

    def test_authority_scheme_reference_and_date_mismatches_quarantine(self):
        self.review_original()
        before = self.client.get(self.base).json()["decisions"]
        for fields in [dict(authority="Unmatched Board"), dict(scheme="other-scheme"), dict(amends="WRONG-ORIGINAL"), dict(published="2026-09-01"), dict(effective="2026-10-01"), dict(published="2026-11-01", effective="2026-11-02")]:
            with self.subTest(fields=fields):
                corr = self.upload(pdf_bytes(notice_text("CORRIGENDUM", **fields)), "CORRIGENDUM")
                url = self.base + f"/amendments/{corr['amendment_id']}"
                preview = self.client.get(url + "/preview").json()
                self.assertFalse(preview["can_apply"])
                self.assertEqual(preview["amendment"]["source_gate"]["recommendation"], "QUARANTINE")
                self.assertEqual(self.client.post(url + "/apply", json=dict(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True)).status_code, 409)
        self.assertEqual(self.client.get(self.base).json()["decisions"], before)
        self.assertEqual(self.client.get(self.base).json()["revision"], 1)

    def test_unsupported_partial_scanned_and_broken_pdfs_cannot_apply(self):
        self.review_original()
        for data in [pdf_bytes(blank=True), b"%PDF- broken", pdf_bytes(notice_text("CORRIGENDUM", body="REPLACE marks-v1 WITH marks-v2 | scope=all_applicants | Minimum qualifying marks: 60%.\nRULE extra | scope=all_applicants | Unsupported exception."))]:
            corr = self.upload(data, "CORRIGENDUM")
            url = self.base + f"/amendments/{corr['amendment_id']}"
            preview = self.client.get(url + "/preview").json()
            self.assertFalse(preview["can_apply"])
            self.assertIsNone(preview["impact"])
            self.assertEqual(self.client.post(url + "/apply", json=dict(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True)).status_code, 409)
        state = self.client.get(self.base).json()
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["decisions"][0]["status"], "FAIL")
        self.assertTrue(all(doc["diagnostics"] for doc in state["documents"][1:]))

    def test_supplied_url_and_duplicate_channel_cannot_upgrade_trust(self):
        self.review_original()
        data = pdf_bytes(notice_text("CORRIGENDUM", reference="FORWARDED"))
        result = self.client.post(self.base + "/documents", files={"file":("forwarded.pdf",data,"application/pdf")},data={"kind":"CORRIGENDUM","source_url":"https://example.gov.in/scholarships"}).json()
        duplicate = self.client.app.state.service.import_pdf("workspace-demo", data, filename="renamed.pdf",kind="CORRIGENDUM",origin_path=self.root / "renamed.pdf")
        self.assertEqual(duplicate.document.document_id, result["document"]["document_id"])
        self.assertEqual(duplicate.document.acquisition_channel, "UPLOAD")
        preview = self.client.get(self.base + f"/amendments/{result['amendment_id']}/preview").json()
        self.assertFalse(preview["can_apply"])
        self.assertEqual(preview["amendment"]["source_gate"]["source_match"], "UNVERIFIED")

    def test_event_insert_failure_rolls_back_review_rules_decisions_and_revision(self):
        self.review_original()
        corr = self.upload(self.corrigendum, "CORRIGENDUM")
        before = self.client.get(self.base).json()
        with self.store.connect(write=True) as con:
            con.execute("CREATE TRIGGER simulate_event_failure BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'test failure'); END")
        response = self.client.post(self.base + f"/amendments/{corr['amendment_id']}/apply", json=dict(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True))
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["error_code"], "DATABASE_ERROR")
        self.assertEqual(self.client.get(self.base).json(), before)
        with self.store.connect() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT count(*) FROM events").fetchone()[0], 0)

    def test_concurrent_apply_has_exactly_one_winner(self):
        self.review_original()
        corr = self.upload(self.corrigendum, "CORRIGENDUM")
        body = ApplyAmendmentRequest(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True)
        def apply():
            try:
                return self.client.app.state.service.apply("workspace-demo", corr["amendment_id"], body).workspace_revision
            except ServiceError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(sorted(results), [2, 409])
        self.assertEqual(len(self.client.get(self.base + "/events").json()["events"]), 1)

    def test_timeline_effective_date_and_known_at_are_independent(self):
        self.review_original()
        self.client.app.state.service.clock = lambda: datetime(2026,10,30,11,tzinfo=timezone.utc)
        corr = self.upload(self.corrigendum, "CORRIGENDUM")
        self.client.post(self.base + f"/amendments/{corr['amendment_id']}/apply", json=dict(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True))
        def timeline(day, known=None):
            args = {"as_of_date":day}
            if known:
                args["known_at"] = known
            response = self.client.get(self.base + "/timeline", params=args)
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()
        self.assertEqual(timeline("2026-10-14")["decisions"][0]["status"], "FAIL")
        self.assertEqual(timeline("2026-10-15")["decisions"][0]["status"], "PASS")
        self.assertEqual(timeline("2026-10-30", "2026-10-30T10:30:00Z")["decisions"][0]["status"], "FAIL")
        self.assertEqual(timeline("2026-10-30", "2026-10-30T09:00:00Z")["decisions"][0]["status"], "UNKNOWN")
        self.assertEqual(self.client.get(self.base + "/timeline", params={"as_of_date":"2026-10-30","known_at":"2026-10-30T10:30:00"}).status_code, 422)

    def test_extraction_cache_is_hash_version_keyed_and_document_bound(self):
        first = self.upload(self.original, "ORIGINAL")
        config = self.store.config("workspace-demo")
        config.workspace_id = "second-workspace"
        config.profiles = [p.model_copy(update={"workspace_id":"second-workspace"}) for p in config.profiles]
        self.store.configure(config)
        second = self.client.post("/api/v1/workspaces/second-workspace/documents", files={"file":("other-name.pdf",self.original,"application/pdf")}, data={"kind":"ORIGINAL"}).json()
        doc = self.store.document("second-workspace", second["document"]["document_id"])
        self.assertEqual(doc.processing_mode, "CACHED_EXTRACTION")
        extraction = self.store.extraction("second-workspace", doc.document_id)
        self.assertEqual(extraction.document_id, doc.document_id)
        self.assertNotEqual(doc.document_id, first["document"]["document_id"])
        self.assertEqual(parse_notice(extraction).rules[0].evidence[0].document_id, doc.document_id)
        with self.store.connect() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM extractions").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT count(*) FROM pdf_sources").fetchone()[0], 1)
        cursor = self.client.get(self.base + "/events").json()["next_cursor"]
        self.assertEqual(self.client.get("/api/v1/workspaces/second-workspace/events", params={"cursor":cursor}).status_code, 400)

    def test_pending_intake_recovers_on_startup(self):
        imported = self.client.app.state.service.import_pdf("workspace-demo", self.original, filename="queued.pdf", kind="ORIGINAL")
        self.assertEqual(self.store.document("workspace-demo", imported.document.document_id).extraction_state.value, "PENDING")
        with TestClient(create_app(self.store, clock=self.client.app.state.service.clock)):
            self.assertEqual(self.store.document("workspace-demo", imported.document.document_id).extraction_state.value, "COMPLETE")

    def test_storage_sources_extractions_acquisition_snapshots_and_events_are_immutable(self):
        self.review_original()
        corr = self.upload(self.corrigendum, "CORRIGENDUM")
        self.client.post(self.base + f"/amendments/{corr['amendment_id']}/apply", json=dict(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True))
        for table, column in [("pdf_sources","sha"),("extractions","id"),("documents","id"),("snapshots","revision"),("events","id")]:
            for query in [f"UPDATE {table} SET {column}={column}", f"DELETE FROM {table}"]:
                with self.subTest(query=query), self.assertRaises(sqlite3.IntegrityError):
                    with self.store.connect(write=True) as con:
                        con.execute(query)

    def test_guard_rejects_edited_candidate_value_scope_and_date(self):
        imported = self.upload(self.original, "ORIGINAL")
        doc = self.store.document("workspace-demo", imported["document"]["document_id"])
        extraction = self.store.extraction("workspace-demo", doc.document_id)
        config = self.store.config("workspace-demo")
        for changes in [dict(min_marks_percent=99),dict(scope_key="other"),dict(effective_from="2026-10-20")]:
            notice = parse_notice(extraction)
            edited = type(notice.rules[0]).model_validate(notice.rules[0].model_dump() | changes)
            notice = replace(notice, rules=(edited,) + notice.rules[1:])
            gate = source_gate(notice, extraction, doc, config, configured_origin=True, checked_at=self.client.app.state.service.clock())
            self.assertEqual(gate.recommendation, GateRecommendation.QUARANTINE)

    def test_openapi_exposes_actual_phase2_contracts(self):
        spec = self.client.get("/openapi.json").json()
        self.assertIn("ReviewOriginalRequest", spec["components"]["schemas"])
        self.assertIn("DocumentExtraction", spec["components"]["schemas"])
        self.assertEqual(spec["components"]["schemas"]["WorkspaceState"]["properties"]["schema_version"]["const"], "1.1.0")
        self.assertEqual(spec["paths"]["/api/v1/workspaces/{workspace_id}/documents"]["post"]["responses"]["202"]["content"]["application/json"]["schema"]["$ref"], "#/components/schemas/ImportDocumentResponse")

    def test_reads_keep_one_snapshot_while_an_apply_commits(self):
        self.review_original()
        corr = self.upload(self.corrigendum, "CORRIGENDUM")
        with self.store.connect() as con:
            first = self.store.row(con, "workspace-demo")["revision"]
            body = ApplyAmendmentRequest(expected_workspace_revision=1,reviewed_by="operator",confirm_source_review=True)
            self.client.app.state.service.apply("workspace-demo",corr["amendment_id"],body)
            self.assertEqual(self.store.row(con,"workspace-demo")["revision"],first)
        self.assertEqual(self.store.state("workspace-demo").revision,2)

    def test_configured_source_with_bad_rule_targets_still_cannot_apply(self):
        bodies = [
            "ADD duplicate-marks | scope=all_applicants | Minimum qualifying marks: 60%.",
            "REPLACE absent-rule WITH new-marks | scope=all_applicants | Minimum qualifying marks: 60%.",
            "REPLACE marks-v1 WITH new-marks | scope=other_scope | Minimum qualifying marks: 60%.",
        ]
        bad_sources = [pdf_bytes(notice_text("CORRIGENDUM",body=body)) for body in bodies]
        config = self.store.config("workspace-demo")
        config.workspace_id = "precedence-workspace"
        config.profiles = [p.model_copy(update={"workspace_id":config.workspace_id}) for p in config.profiles]
        config.configured_hashes += [hashlib.sha256(data).hexdigest() for data in bad_sources]
        self.store.configure(config)
        base = "/api/v1/workspaces/precedence-workspace"
        original = self.client.post(base + "/documents", files={"file":("original.pdf",self.original,"application/pdf")},data={"kind":"ORIGINAL"}).json()
        self.assertEqual(self.client.post(base + f"/documents/{original['document']['document_id']}/review",json=dict(expected_workspace_revision=0,reviewed_by="operator",confirm_source_review=True)).status_code,200)
        for data in bad_sources:
            corr = self.client.post(base + "/documents",files={"file":("bad-target.pdf",data,"application/pdf")},data={"kind":"CORRIGENDUM"}).json()
            preview = self.client.get(base + f"/amendments/{corr['amendment_id']}/preview").json()
            self.assertFalse(preview["can_apply"])
            self.assertEqual(preview["amendment"]["source_gate"]["recommendation"],"QUARANTINE")
            self.assertTrue(any(c["check_id"]=="rule_precedence" for c in preview["amendment"]["source_gate"]["checks"]))
        self.assertEqual(self.client.get(base).json()["revision"],1)
