"""Synthetic end-to-end tests; not proof of live monitoring."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.exam_store import ExamStore
from backend.tests.local_temp import LocalTemporaryDirectory


@pytest.fixture
def client():
    directory = LocalTemporaryDirectory()
    store = ExamStore(Path(directory.name) / "app.sqlite3")
    with TestClient(create_app(store, enable_watchers=False, v2_demo=True)) as connected:
        yield connected
    directory.cleanup()


def session(client, persona):
    response = client.post("/api/v2/demo/session", json={"persona":persona})
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization":"Bearer " + payload["access_token"]}, payload


def test_subscription_review_fanout_and_private_inbox(client):
    catalog = client.get("/api/v2/catalog").json()
    assert {"jee-main","neet-ug","nda-na","gate","upsc-ese","ssc-je"}.issubset({e["exam_id"] for e in catalog["exams"]})
    student, _ = session(client,"school")
    engineer, _ = session(client,"engineering")
    admin, operator = session(client,"operator")
    for cycle, headers in [("jee-main:2027:s1",student),("gate:2027",engineer)]:
        response = client.post("/api/v2/me/subscriptions",headers=headers,json={"cycle_id":cycle,"topics":["ALL"],"application_status":"INTERESTED"})
        assert response.status_code == 200,response.text
    assert client.get("/api/v2/me/notifications",headers=student).json()["notifications"] == []
    detected = client.post("/api/v2/admin/demo/replay",headers=admin).json()
    notice = next(n for n in detected if n["cycle_id"]=="jee-main:2027:s1")
    assert notice["source_kind"] == "LOCAL_DEMO_FIXTURE"
    body = dict(notice_id=notice["notice_id"],reviewer_id=operator["user_id"],action="APPROVE",reason="Reviewed synthetic evidence",reviewed_at=datetime.now(timezone.utc).isoformat(),expected_revision=notice["revision"])
    url=f"/api/v2/admin/notices/{notice['notice_id']}/review"
    response=client.post(url,headers=admin,json=body)
    assert response.status_code==200,response.text
    assert client.post(url,headers=admin,json=body).status_code==200
    notifications=client.get("/api/v2/me/notifications",headers=student).json()["notifications"]
    assert len(notifications)==1
    assert "SYNTHETIC" in notifications[0]["headline"]
    assert client.get("/api/v2/me/notifications",headers=engineer).json()["notifications"]==[]
    notification_id=notifications[0]["notification_id"]
    assert client.post(f"/api/v2/me/notifications/{notification_id}/read",headers=engineer).status_code==404
    assert client.post(f"/api/v2/me/notifications/{notification_id}/read",headers=student).json()["delivery"]=="READ"
    item=client.get(f"/api/v2/me/notifications/{notification_id}",headers=student).json()
    assert item["match"]["relevance"]=="GENERAL_UPDATE"
    assert item["match"]["before"] is None and item["match"]["after"] is None
    totals=client.get("/api/v2/admin/dashboard",headers=admin).json()["totals"]
    assert totals["registered_users"]==2
    assert totals["active_subscriptions"]==2
    assert totals["notifications_delivered"]==1 and totals["notifications_read"]==1


def test_roles_ownership_topic_filters_and_no_implicit_personal_data(client):
    student,_=session(client,"school")
    engineer,_=session(client,"engineering")
    admin,operator=session(client,"operator")
    assert client.get("/api/v2/me/subscriptions").status_code==401
    assert client.get("/api/v2/admin/dashboard",headers=student).status_code==403
    assert client.patch("/api/v2/me/profile",headers=student,json={"date_of_birth":"2007-01-01"}).status_code==422
    sub=client.post("/api/v2/me/subscriptions",headers=student,json={"cycle_id":"jee-main:2027:s1","topics":["RESULTS"]}).json()
    assert client.delete(f"/api/v2/me/subscriptions/{sub['subscription_id']}",headers=engineer).status_code==404
    notices=client.post("/api/v2/admin/demo/replay",headers=admin).json()
    notice=next(n for n in notices if n["cycle_id"]=="jee-main:2027:s1")
    response=client.post(f"/api/v2/admin/notices/{notice['notice_id']}/review",headers=admin,json=dict(notice_id=notice["notice_id"],reviewer_id=operator["user_id"],action="APPROVE",reason="Synthetic topic test",reviewed_at=datetime.now(timezone.utc).isoformat(),expected_revision=0))
    assert response.status_code==200,response.text
    assert client.get("/api/v2/me/notifications",headers=student).json()["notifications"]==[]
    assert client.get("/api/v1/health").json()["schema_version"]=="1.1.0"
