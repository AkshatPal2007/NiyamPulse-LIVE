from datetime import datetime,timezone
import json

import pytest

from backend.services.source_monitor import FetchResult,ListingLink
from tests.test_v2_flow import client,session


def review_body(notice,operator,**changes):
    return dict(notice_id=notice['notice_id'],reviewer_id=operator['user_id'],action='APPROVE',reason='Reviewed explicit synthetic source evidence',reviewed_at=datetime.now(timezone.utc).isoformat(),expected_revision=notice['revision'])|changes


def test_publication_failure_rolls_back_entire_fanout(client):
    learner,_=session(client,'school');admin,operator=session(client,'operator')
    client.post('/api/v2/me/subscriptions',headers=learner,json={'cycle_id':'jee-main:2027:s1'})
    notice=client.post('/api/v2/admin/demo/replay',headers=admin).json()[0]
    with client.app.state.exam_store.connect(write=True) as con:
        con.execute("CREATE TRIGGER test_v2_delivery_failure BEFORE INSERT ON v2_notifications BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    result=client.post(f"/api/v2/admin/notices/{notice['notice_id']}/review",headers=admin,json=review_body(notice,operator))
    assert result.status_code==500 and result.json()['code']=='DATABASE_ERROR'
    with client.app.state.exam_store.connect() as con:
        for table in ['v2_updates','v2_matches','v2_notifications','v2_reviews']:assert con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0
        assert json.loads(con.execute('SELECT payload FROM v2_notices WHERE id=?',(notice['notice_id'],)).fetchone()[0])['review_status']=='NEEDS_REVIEW'


def test_changed_review_identity_revision_and_frozen_text_are_rejected(client):
    admin,operator=session(client,'operator')
    notice=client.post('/api/v2/admin/demo/replay',headers=admin).json()[0]
    url=f"/api/v2/admin/notices/{notice['notice_id']}/review"
    assert client.post(url,headers=admin,json=review_body(notice,operator,reviewer_id='forged-reviewer')).status_code==403
    assert client.post(url,headers=admin,json=review_body(notice,operator,expected_revision=5)).status_code==409
    with client.app.state.exam_store.connect(write=True) as con:
        con.execute('UPDATE v2_notices SET pages=? WHERE id=?',(json.dumps(['Forged extraction']),notice['notice_id']))
    assert client.post(url,headers=admin,json=review_body(notice,operator)).status_code==409


def test_opt_in_removal_account_deletion_and_session_revocation(client):
    learner,_=session(client,'school')
    result=client.patch('/api/v2/me/profile',headers=learner,json={'personalization_opt_in':True,'marks_percent':80,'date_of_birth':'2007-01-01'})
    assert result.status_code==200
    assert client.delete('/api/v2/me/profile/personalization',headers=learner).status_code==204
    profile=client.get('/api/v2/me/profile',headers=learner).json()
    assert profile['marks_percent'] is None and profile['date_of_birth'] is None and not profile['personalization_opt_in']
    assert client.delete('/api/v2/me/account',headers=learner).status_code==204
    assert client.get('/api/v2/me/profile',headers=learner).status_code==401
    client.app.state.exam_store.seed_demo_users()
    assert client.post('/api/v2/demo/session',json={'persona':'school'}).status_code==404


def test_inbox_newest_first_pagination_is_private_and_idempotent(client):
    learner,_=session(client,'school');other,_=session(client,'engineering');admin,operator=session(client,'operator')
    client.post('/api/v2/me/subscriptions',headers=learner,json={'cycle_id':'jee-main:2027:s1'})
    monitor=client.app.state.source_monitor
    ids=[]
    for index in range(3):
        text=f'SYNTHETIC DEMO registration update {index}. No actual deadline is asserted.'
        url=f'https://demo.invalid/registration-{index}'
        notice,_=monitor.ingest(None,ListingLink(f'JEE Main 2027 Session 1 registration {index}',url,'jee-main:2027:s1'),FetchResult(url,url,text.encode(),'text/plain',200),offline=True)
        body=review_body(notice.model_dump(mode='json'),operator)
        response=client.post(f'/api/v2/admin/notices/{notice.notice_id}/review',headers=admin,json=body)
        assert response.status_code==200,response.text
        assert client.post(f'/api/v2/admin/notices/{notice.notice_id}/review',headers=admin,json=body).status_code==200
        ids.append(notice.notice_id)
    first=client.get('/api/v2/me/notifications?limit=1',headers=learner).json()
    assert first['notifications'][0]['headline'].endswith('registration 2') and first['unread_count']==3
    cursor=first['next_cursor']
    assert client.get('/api/v2/me/notifications',headers=other,params={'cursor':cursor}).status_code==400
    second=client.get('/api/v2/me/notifications',headers=learner,params={'cursor':cursor,'limit':1}).json()
    assert second['notifications'][0]['headline'].endswith('registration 1')
    assert len(client.get('/api/v2/me/notifications',headers=learner).json()['notifications'])==3


def test_extraction_cannot_be_rebound_to_unrelated_source_bytes(client):
    admin,operator=session(client,'operator')
    notices=client.post('/api/v2/admin/demo/replay',headers=admin).json()
    notice,unrelated=notices
    with client.app.state.exam_store.connect(write=True) as con:
        other=con.execute('SELECT pages,extraction_id FROM v2_notices WHERE id=?',(unrelated['notice_id'],)).fetchone()
        forged=json.loads(json.dumps(notice))
        forged['evidence']=unrelated['evidence']
        for anchor in forged['evidence']:
            anchor['document_id']=notice['notice_id'];anchor['document_sha256']=notice['document_sha256']
        con.execute('UPDATE v2_notices SET pages=?,extraction_id=?,payload=? WHERE id=?',(other['pages'],other['extraction_id'],json.dumps(forged),notice['notice_id']))
    response=client.post(f"/api/v2/admin/notices/{notice['notice_id']}/review",headers=admin,json=review_body(notice,operator))
    assert response.status_code==409,response.text
