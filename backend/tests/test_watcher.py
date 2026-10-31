from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import time
import unittest

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.storage import Store, WorkspaceConfig
from backend.tests.local_temp import LocalTemporaryDirectory
from backend.tests.pdf_support import notice_text, pdf_bytes
from backend.tests.support import profile


class WatcherTests(unittest.TestCase):
    def test_native_local_watcher_detects_new_pdf_without_auto_apply_and_deduplicates(self):
        temp = LocalTemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        intake = root / "intake"
        intake.mkdir()
        original = pdf_bytes()
        corrigendum = pdf_bytes(notice_text("CORRIGENDUM"))
        store = Store(root / "app.sqlite3")
        store.configure(WorkspaceConfig(workspace_id="workspace-demo",scheme_id="scholarship-demo-2026",
                                         issuing_authority="Synthetic Scholarship Board", synthetic=True,
                                         evaluation_date=date(2026,10,30), profiles=[profile(marks_percent=65)],
                                         configured_hashes=[hashlib.sha256(original).hexdigest()], intake_directory=str(intake)))
        base = "/api/v1/workspaces/workspace-demo"
        with TestClient(create_app(store, legacy_api_test=True, clock=lambda:datetime(2026,10,30,10,tzinfo=timezone.utc))) as client:
            imported = client.post(base + "/documents",files={"file":("original.pdf",original,"application/pdf")},data={"kind":"ORIGINAL"}).json()
            reviewed = client.post(base + f"/documents/{imported['document']['document_id']}/review", json=dict(expected_workspace_revision=0,reviewed_by="operator",confirm_source_review=True))
            self.assertEqual(reviewed.status_code,200,reviewed.text)
            (intake / "new-corrigendum.pdf").write_bytes(corrigendum)
            deadline = time.monotonic() + 8
            state = None
            while time.monotonic() < deadline:
                state = client.get(base).json()
                if state["amendments"] and state["amendments"][0]["intake_state"] == "READY_TO_APPLY":
                    break
                time.sleep(0.05)
            self.assertTrue(state["amendments"], state)
            self.assertEqual(state["amendments"][0]["intake_state"], "READY_TO_APPLY")
            self.assertEqual(state["documents"][1]["sha256"],hashlib.sha256(corrigendum).hexdigest())
            self.assertEqual(state["documents"][1]["acquisition_channel"], "LOCAL_WATCH")
            self.assertTrue(state["watcher"]["running"])
            self.assertEqual(state["revision"],1)
            self.assertEqual(state["decisions"][0]["status"],"FAIL")
            (intake / "same-content-new-name.pdf").write_bytes(corrigendum)
            watcher = client.app.state.watchers["workspace-demo"]
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and len(watcher.processed) < 2:
                time.sleep(0.05)
            self.assertEqual(len(watcher.processed),2)
            self.assertEqual(len(client.get(base).json()["documents"]),2)
            self.assertEqual(client.get(base + "/events").json()["events"],[])
        self.assertFalse(watcher.health().running)
