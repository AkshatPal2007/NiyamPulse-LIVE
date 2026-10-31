from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from backend.demo_setup import setup_demo
from backend.main import create_app
from backend.tests.local_temp import LocalTemporaryDirectory


class DemoSetupTests(unittest.TestCase):
    def test_setup_is_reproducible_and_full_pdf_pipeline_matches_phase1_gold(self):
        temp = LocalTemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        store, fixtures = setup_demo(root / "data", root / "pdf")
        _, repeated = setup_demo(root / "data", root / "pdf")
        self.assertEqual(fixtures, repeated)
        workspace = "scholarship-demo-2026"
        self.assertEqual(store.state(workspace).revision, 0)
        self.assertEqual(store.state(workspace).documents, [])
        base = f"/api/v1/workspaces/{workspace}"
        from datetime import datetime, timezone
        with TestClient(create_app(store, legacy_api_test=True, clock=lambda:datetime(2026,10,30,10,tzinfo=timezone.utc))) as client:
            original = client.post(base + "/documents", files={"file":("original.pdf",fixtures["synthetic_original.pdf"],"application/pdf")},data={"kind":"ORIGINAL"}).json()
            result = client.post(base + f"/documents/{original['document']['document_id']}/review",json=dict(expected_workspace_revision=0,reviewed_by="test_operator",confirm_source_review=True))
            self.assertEqual(result.status_code,200,result.text)
            corr = client.post(base + "/documents", files={"file":("corr.pdf",fixtures["synthetic_corrigendum.pdf"],"application/pdf")},data={"kind":"CORRIGENDUM"}).json()
            event = client.post(base + f"/amendments/{corr['amendment_id']}/apply",json=dict(expected_workspace_revision=1,reviewed_by="test_operator",confirm_source_review=True)).json()["event"]
            self.assertEqual(event["counts"],dict(evaluated=5,changed=2,improved=1,worsened=0,review_required=1,unchanged=3))
            mismatch = client.post(base + "/documents", files={"file":("mismatch.pdf",fixtures["synthetic_mismatch.pdf"],"application/pdf")},data={"kind":"CORRIGENDUM"}).json()
            preview = client.get(base + f"/amendments/{mismatch['amendment_id']}/preview").json()
            self.assertFalse(preview["can_apply"])
            self.assertEqual(preview["amendment"]["source_gate"]["recommendation"], "QUARANTINE")
