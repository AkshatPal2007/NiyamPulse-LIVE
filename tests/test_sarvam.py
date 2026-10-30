"""Offline transport tests; no Sarvam credentials or paid requests."""
import json
from datetime import datetime, timezone
import httpx
import pytest
from backend import schemas as s
from backend.services.sarvam import SarvamService, validate_candidate
from backend.services.source_monitor import SourceMonitor
from backend.storage import ServiceError
from tests.test_v2_flow import client, session


def candidate(quote='SYNTHETIC DEMO ONLY. This is a test registration announcement for JEE Main 2027 Session 1.'):
    return {'cycle_id':'jee-main:2027:s1','notice_type':'INFORMATIONAL','topics':['REGISTRATION'], 'facts':[{'kind':'ANNOUNCEMENT','page_number':1,'literal_quote':quote,'date_value':None}], 'requires_rule_validation':False}


def setup_service(client, payload=None, status=200):
    store=client.app.state.exam_store
    notice=SourceMonitor(store).replay_demo()[0]
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(status,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload or candidate())}}], 'usage':{'prompt_tokens':100,'completion_tokens':80,'total_tokens':180}})
    svc=SarvamService(store,api_key='test-key',transport=httpx.MockTransport(handler))
    svc.set_budget(5000)
    client.app.state.sarvam_service=svc
    return svc,notice,calls


def test_validated_cached_extraction_and_hindi_template(client):
    svc,notice,calls=setup_service(client)
    result=svc.process(notice.notice_id,0)
    assert result.status=='VALIDATED' and result.summary_hi and result.provider=='SARVAM_105B'
    assert result.evidence[0].literal_quote==candidate()['facts'][0]['literal_quote']
    assert len(calls)==1 and 'test-key'==calls[0].headers['api-subscription-key']
    assert json.loads(calls[0].content)['reasoning_effort'] is None
    assert svc.process(notice.notice_id,1).cache_hit
    assert len(calls)==1 and svc.health().reserved_paise==500
    assert svc.health().prompt_tokens==100
    updated=client.app.state.exam_service.notice_detail(notice.notice_id)
    assert updated.notice.revision==1 and updated.notice.review_status=='NEEDS_REVIEW'
    assert updated.notice.processing_mode=='OFFLINE_REPLAY'


@pytest.mark.parametrize('mutation',[
    {'cycle_id':'gate:2027'},
    {'facts':[{'kind':'ANNOUNCEMENT','page_number':1,'literal_quote':'You are approved for admission.','date_value':None}]},
    {'facts':[{'kind':'APPLICATION_DEADLINE','page_number':1,'literal_quote':candidate()['facts'][0]['literal_quote'],'date_value':'2027-12-31'}]},
    {'decision':'PASS'},
])
def test_unsupported_ai_output_never_modifies_notice_or_inbox(client,mutation):
    svc,notice,calls=setup_service(client,candidate()|mutation)
    result=svc.process(notice.notice_id,0)
    assert result.status=='GUARD_REJECTED'
    assert client.app.state.exam_service.notice_detail(notice.notice_id).notice.revision==0
    admin,operator=session(client,'operator')
    body={'notice_id':notice.notice_id,'reviewer_id':operator['user_id'],'action':'APPROVE','reason':'Attempt to bypass rejected synthetic candidate','reviewed_at':datetime.now(timezone.utc).isoformat(),'expected_revision':0}
    blocked=client.post('/api/v2/admin/notices/'+notice.notice_id+'/review',headers=admin,json=body)
    assert blocked.status_code==409 and blocked.json()['code']=='ANALYSIS_GUARD_BLOCKED'
    with svc.store.connect() as con:
        assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==0


def test_budget_and_http_failure_are_persisted_without_secret_leak(client):
    svc,notice,calls=setup_service(client,status=429)
    svc.set_budget(400)
    with pytest.raises(ServiceError) as error: svc.process(notice.notice_id,0)
    assert error.value.code=='SARVAM_BUDGET_EXCEEDED' and not calls
    svc.set_budget(500)
    with pytest.raises(ServiceError) as error: svc.process(notice.notice_id,0)
    assert error.value.code=='SARVAM_RATE_LIMITED' and 'test-key' not in str(error.value)
    assert svc.health().reserved_paise==500
    with pytest.raises(ServiceError):svc.process(notice.notice_id,0)
    assert len(calls)==1


def test_dates_and_false_topic_mapping_fail_closed():
    pages=['Application deadline: 31 October 2026.']
    item=candidate('Application deadline: 31 October 2026.')
    item['facts'][0]|={'kind':'APPLICATION_DEADLINE','date_value':'2026-10-31'}
    validate_candidate(s.SarvamCandidate.model_validate(item),pages,'jee-main:2027:s1')
    item['facts'][0]['date_value']='2026-11-30'
    with pytest.raises(ValueError):validate_candidate(s.SarvamCandidate.model_validate(item),pages,'jee-main:2027:s1')
    item=candidate();item['topics']=['RESULTS']
    with pytest.raises(ValueError):validate_candidate(s.SarvamCandidate.model_validate(item),[candidate()['facts'][0]['literal_quote']],'jee-main:2027:s1')


def test_only_operator_can_process_and_stale_revision_is_rejected(client):
    svc,notice,calls=setup_service(client)
    learner,_=session(client,'school');admin,_=session(client,'operator')
    url='/api/v2/admin/notices/'+notice.notice_id+'/analyze'
    assert client.post(url,headers=learner,json={'expected_revision':0}).status_code==403
    assert client.post(url,headers=admin,json={'expected_revision':9}).status_code==409
    assert not calls
    assert client.post(url,headers=admin,json={'expected_revision':0}).status_code==200


def test_whitespace_only_quote_is_resolved_to_exact_frozen_span(client):
    svc,notice,calls=setup_service(client)
    from backend.services.source_monitor import FetchResult,ListingLink
    text='JEE Main 2027\nRegistration announcement.'
    notice,_=SourceMonitor(svc.store).ingest(None,ListingLink('JEE registration','https://demo.invalid/spacing','jee-main:2027:s1'),FetchResult('https://demo.invalid/spacing','https://demo.invalid/spacing',text.encode(),'text/plain',200),offline=True)
    def response(_):return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(candidate('JEE Main 2027 Registration announcement.'))}}]})
    svc.transport=httpx.MockTransport(response)
    result=svc.process(notice.notice_id,0)
    assert result.status=='VALIDATED' and result.evidence[0].literal_quote==text
    assert svc.process(notice.notice_id,1).cache_hit


def test_localized_publication_and_mutated_summary_rejected(client):
    svc,notice,calls=setup_service(client)
    learner,_=session(client,'school');admin,operator=session(client,'operator')
    client.post('/api/v2/me/subscriptions',headers=learner,json={'cycle_id':notice.cycle_id})
    client.patch('/api/v2/me/profile',headers=learner,json={'preferred_language':'hi'})
    result=svc.process(notice.notice_id,0)
    with svc.store.connect(write=True) as con:
        data=json.loads(con.execute('SELECT payload FROM v2_notice_analysis WHERE notice_id=?',(notice.notice_id,)).fetchone()[0]);data['summary_hi']='Invented deadline 2099-01-01';con.execute('UPDATE v2_notice_analysis SET payload=? WHERE notice_id=?',(json.dumps(data),notice.notice_id))
    body={'notice_id':notice.notice_id,'reviewer_id':operator['user_id'],'action':'APPROVE','reason':'Reviewed synthetic exact source facts','reviewed_at':datetime.now(timezone.utc).isoformat(),'expected_revision':1}
    url='/api/v2/admin/notices/'+notice.notice_id+'/review'
    assert client.post(url,headers=admin,json=body).status_code==409
    with svc.store.connect(write=True) as con:con.execute('UPDATE v2_notice_analysis SET payload=? WHERE notice_id=?',(result.model_dump_json(),notice.notice_id))
    assert client.post(url,headers=admin,json=body).status_code==200
    notification=client.get('/api/v2/me/notifications',headers=learner).json()['notifications'][0]
    assert notification['language']=='hi' and notification['body']==result.summary_hi
    assert notification['evidence'][0]['literal_quote']==result.evidence[0].literal_quote


def test_uncertain_and_incomplete_provider_responses_hold_notice(client):
    svc,notice,calls=setup_service(client)
    svc.transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':None}}]}))
    assert svc.process(notice.notice_id,0).status=='GUARD_REJECTED'
    assert svc.store.catalog().schema_version=='2.0.0'


def test_controlled_hindi_copies_only_exact_labeled_source_values():
    from backend.services.sarvam import render_summaries
    item=candidate('Last Date for Receipt of Applications\n06/10/2026 - 6:00pm')
    en,hi=render_summaries(s.SarvamCandidate.model_validate(item))
    assert '06/10/2026 - 6:00pm' in hi and 'अंतिम तारीख' in hi
    assert en in hi and '2027-12-31' not in hi


def test_malformed_provider_json_shape_returns_typed_failure_and_records_reservation(client):
    svc,notice,calls=setup_service(client)
    svc.transport=httpx.MockTransport(lambda _:httpx.Response(200,json=[]))
    with pytest.raises(ServiceError) as error:svc.process(notice.notice_id,0)
    assert error.value.code=='SARVAM_INVALID_RESPONSE'
    assert svc.health().reserved_paise==500 and svc.health().status=='ERROR'
