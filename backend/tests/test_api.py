from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.storage import Store, WorkspaceConfig
from backend.tests.pdf_support import notice_text, pdf_bytes
from backend.tests.support import profile
from backend.tests.local_temp import LocalTemporaryDirectory


class APIHarness(unittest.TestCase):
    def setUp(self):
        self.temp = LocalTemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = pdf_bytes()
        self.corrigendum = pdf_bytes(notice_text("CORRIGENDUM"))
        self.store = Store(self.root / "app.sqlite3")
        self.store.configure(WorkspaceConfig(
            workspace_id="workspace-demo", scheme_id="scholarship-demo-2026",
            issuing_authority="Synthetic Scholarship Board", synthetic=True,
            evaluation_date=date(2026, 10, 30),
            configured_hashes=[hashlib.sha256(b).hexdigest() for b in (self.original, self.corrigendum)],
            profiles=[profile(marks_percent=65)],
        ))
        self.client = TestClient(create_app(self.store, legacy_api_test=True, clock=lambda: datetime(2026, 10, 30, 10, tzinfo=timezone.utc)))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.base = "/api/v1/workspaces/workspace-demo"

    def upload(self, data, kind):
        result = self.client.post(self.base + "/documents", files={"file": ("synthetic.pdf", data, "application/pdf")}, data={"kind": kind})
        self.assertEqual(result.status_code, 202, result.text)
        return result.json()

    def review_original(self):
        imported = self.upload(self.original, "ORIGINAL")
        result = self.client.post(self.base + f"/documents/{imported['document']['document_id']}/review", json={"expected_workspace_revision": 0,"reviewed_by":"synthetic_operator","confirm_source_review":True})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["revision"], 1)
        return imported


class APITests(APIHarness):
    def test_reviewed_pdf_apply_changes_real_decision_and_persists_event(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        original = self.review_original()
        state = self.client.get(self.base).json()
        self.assertEqual(state["decisions"][0]["status"], "FAIL")
        corr = self.upload(self.corrigendum, "CORRIGENDUM")
        amendment_id = corr["amendment_id"]
        preview = self.client.get(self.base + f"/amendments/{amendment_id}/preview")
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertTrue(preview.json()["can_apply"])
        self.assertEqual(preview.json()["impact"]["counts"]["improved"], 1)
        self.assertEqual(self.client.get(self.base).json()["revision"], 1)
        body = {"expected_workspace_revision":1,"reviewed_by":"synthetic_operator","confirm_source_review":True}
        response = self.client.post(self.base + f"/amendments/{amendment_id}/apply", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        event = response.json()["event"]
        self.assertEqual(event["event_kind"], "APPLIED")
        self.assertEqual(event["transitions"][0]["after"]["status"], "PASS")
        self.assertEqual(self.client.post(self.base + f"/amendments/{amendment_id}/apply", json=body).status_code, 409)
        feed = self.client.get(self.base + "/events").json()
        self.assertEqual([e["event_id"] for e in feed["events"]], [event["event_id"]])
        self.assertEqual(self.client.get(self.base + "/events", params={"cursor":feed["next_cursor"]}).json()["events"], [])
        document_id = original["document"]["document_id"]
        self.assertEqual(self.client.get(self.base + f"/documents/{document_id}/pdf").content, self.original)
        extraction = self.client.get(self.base + f"/documents/{document_id}/extraction").json()
        self.assertEqual(extraction["pages"][0]["page_number"], 1)
        self.assertEqual(Store(self.root / "app.sqlite3").state("workspace-demo").revision, 2)

    def test_untrusted_source_cannot_apply_or_change_decisions(self):
        self.review_original()
        data = pdf_bytes(notice_text("CORRIGENDUM", reference="UNTRUSTED-01"))
        corr = self.upload(data, "CORRIGENDUM")
        url = self.base + f"/amendments/{corr['amendment_id']}"
        before = self.client.get(self.base).json()["decisions"]
        preview = self.client.get(url + "/preview").json()
        self.assertFalse(preview["can_apply"])
        self.assertEqual(preview["amendment"]["source_gate"]["recommendation"], "MANUAL_REVIEW")
        response = self.client.post(url + "/apply", json={"expected_workspace_revision":1,"reviewed_by":"operator","confirm_source_review":True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(self.base).json()["decisions"], before)
        self.assertEqual(self.client.get(self.base + "/events").json()["events"], [])

    def test_errors_are_typed_and_no_fake_evaluation(self):
        for response in [self.client.get("/missing"), self.client.get("/api/v1/workspaces/missing"), self.client.get(self.base + "/events", params={"cursor":"tampered"}), self.client.get(self.base + "/evaluations/latest"), self.client.post(self.base + "/documents", files={"file":("x.pdf",b"bad","application/pdf")},data={"kind":"ORIGINAL"})]:
            self.assertGreaterEqual(response.status_code, 400)
            self.assertIn("error_code", response.json())
            self.assertIn("request_id", response.json())
