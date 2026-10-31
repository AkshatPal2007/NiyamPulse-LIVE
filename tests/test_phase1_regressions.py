"""Regression tests from the full project audit; synthetic, no network."""
from datetime import date
import pytest
from backend import schemas as s
from backend.services.rule_bridge import facts_to_notice_changes,apply_rule_bridge
from backend.services.rule_engine import EngineError

CYCLE='jee-main:2027:s1'

def decode(quote,kind='RULE_CANDIDATE',before=()):
    fact=s.ExtractedFact(kind=kind,page_number=1,literal_quote=quote)
    anchor=s.EvidenceAnchor(document_id='audit-notice',document_sha256='a'*64,extraction_id='audit-extract',page_number=1,literal_quote=quote,start_char=0,end_char=len(quote))
    return facts_to_notice_changes(notice_id='audit-notice',cycle_id=CYCLE,facts=[fact],evidence_anchors=[anchor],before_rules=before)

def contextual(clause,operation='ADD',target=None):
    return f'Published: 2027-01-01 | Effective: 2027-02-01 | Scheme: {CYCLE} | Operation: {operation} | '+(f'Target: {target} | ' if target else '')+'Scope: all_applicants | '+clause

@pytest.mark.parametrize('quote',[
 'Applicants with less than 60% marks are exempt from the minimum marks requirement.',
 'Documents required: passport.',
 'Application deadline: 06/07/2027',
 'Minimum qualifying marks: 75%.',
 'Age limit between 18 and 30 years.',
])
def test_ambiguous_source_abstains(quote):
    changes,diags=decode(quote)
    assert not changes and diags

@pytest.mark.parametrize('clause,rule_type',[
 ('Minimum qualifying marks: 75%.','minimum_marks'),
 ('Maximum annual household income: INR 29000.','maximum_income_inr'),
 ('Application deadline: 2027-03-14.','application_deadline'),
 ('Age bounds: 18..30 years on 2027-01-01.','age_bounds'),
 ('Required documents: PASSPORT.','required_documents'),
])
def test_explicit_context_is_reproducible(clause,rule_type):
    q=contextual(clause)
    first,diags=decode(q);second,_=decode(q)
    assert not diags and first[0].rule_type.value==rule_type
    assert first==second
    assert first[0].effective_from==date(2027,2,1)
    if rule_type=='required_documents':assert first[0].proposed_rule.required_document_codes==['PASSPORT']


def test_unattested_change_cannot_self_verify():
    changes,_=decode(contextual('Minimum qualifying marks: 75%.'))
    with pytest.raises(EngineError):apply_rule_bridge(notice_changes=changes,before_rules=[],before_verified_hashes=frozenset(),scheme_id=CYCLE,cycle_id=CYCLE,subscribers=[],as_of_date=date(2027,2,1))


def attest(changes,cycle=CYCLE):
    from backend.services.rule_bridge import _build_amendment_change
    from backend.services.amendments import change_fingerprint
    from backend.services.rule_engine import rule_fingerprint
    return dict(verified_change_hashes=frozenset(change_fingerprint(_build_amendment_change(c,cycle,c.evidence)) for c in changes),verified_proposed_rule_hashes=frozenset(rule_fingerprint(c.proposed_rule) for c in changes if c.proposed_rule))


def test_replace_revoke_roundtrip_and_stale_revision():
    from pathlib import Path
    from backend.tests.local_temp import LocalTemporaryDirectory
    from backend.exam_store import ExamStore
    from backend.services.rule_engine import evaluate_applicant,rule_set_fingerprint
    from backend.storage import ServiceError
    from tests.test_v2_rule_bridge import _minimal_notice_and_update,_applicant,NOW
    temp=LocalTemporaryDirectory()
    try:
        store=ExamStore(Path(temp.name)/'roundtrip.sqlite3')
        history,hashes=[],frozenset()
        for revision,(clause,operation) in enumerate([('Minimum qualifying marks: 75%.','ADD'),('Minimum qualifying marks: 60%.','REPLACE'),('Rule type: minimum_marks.','REVOKE')]):
            target=None if operation=='ADD' else history[-1].rule_id
            # The current replacement is the only open rule; history order is sorted by ID.
            if operation!='ADD':target=next(r.rule_id for r in history if r.effective_until is None)
            q=contextual(clause,operation,target).replace('Effective: 2027-02-01',f'Effective: 2027-0{revision+2}-01')
            changes,diags=decode(q,before=history);assert not diags
            plan=apply_rule_bridge(notice_changes=changes,before_rules=history,before_verified_hashes=hashes,scheme_id=CYCLE,cycle_id=CYCLE,subscribers=[],as_of_date=date(2027,revision+2,2),**attest(changes))
            _,update=_minimal_notice_and_update(store,CYCLE)
            with store.connect(write=True) as con:store.persist_rule_changes(con,cycle_id=CYCLE,update_id=update.update_id,bridge_result=plan,now_text=NOW.isoformat(),expected_revision=revision)
            with store.connect() as con:history,hashes=store.rule_set_for_cycle(con,CYCLE)
            assert list(plan.after_rules)==history
            assert rule_set_fingerprint(history,verified_rule_hashes=hashes)==plan.after_rule_set_sha256
            expected=['FAIL','PASS','UNKNOWN'][revision]
            assert evaluate_applicant(_applicant('synthetic-roundtrip',65),history,scheme_id=CYCLE,as_of_date=date(2027,revision+2,2),verified_rule_hashes=hashes).status.value==expected
        _,update=_minimal_notice_and_update(store,CYCLE)
        with pytest.raises(ServiceError) as error:
            with store.connect(write=True) as con:store.persist_rule_changes(con,cycle_id=CYCLE,update_id=update.update_id,bridge_result=plan,now_text=NOW.isoformat(),expected_revision=0)
        assert error.value.code=='STALE_RULE_REVISION'
    finally:temp.cleanup()


def test_unsupported_member_holds_entire_batch():
    q=contextual('Minimum qualifying marks: 75%.')
    facts=[s.ExtractedFact(kind='RULE_CANDIDATE',page_number=1,literal_quote=q),s.ExtractedFact(kind='UNSUPPORTED_REQUIREMENT',page_number=1,literal_quote='Must meet unsupported medical criteria.')]
    anchor=s.EvidenceAnchor(document_id='audit-notice',document_sha256='a'*64,extraction_id='audit-extract',page_number=1,literal_quote=q,start_char=0,end_char=len(q))
    changes,diags=facts_to_notice_changes(notice_id='audit-notice',cycle_id=CYCLE,facts=facts,evidence_anchors=[anchor])
    assert not changes and diags


def test_future_publication_does_not_precede_acquisition():
 q=contextual('Minimum qualifying marks: 75%.')
 fact=s.ExtractedFact(kind='RULE_CANDIDATE',page_number=1,literal_quote=q)
 anchor=s.EvidenceAnchor(document_id='audit-notice',document_sha256='a'*64,extraction_id='audit-extract',page_number=1,literal_quote=q,start_char=0,end_char=len(q))
 changes,diags=facts_to_notice_changes(notice_id='audit-notice',cycle_id=CYCLE,facts=[fact],evidence_anchors=[anchor],observed_on=date(2026,10,31))
 assert not changes and diags


from tests.test_v2_flow import client,session
import httpx,json
from datetime import datetime,timezone
from backend.services.source_monitor import SourceMonitor,ListingLink,FetchResult
from backend.services.sarvam import SarvamService


def analyze_fixture(client,clause):
 q=contextual(clause).replace('2027-01-01','2026-01-01').replace('2027-02-01','2026-02-01')
 url='https://demo.invalid/'+str(abs(hash(q)))
 notice,_=SourceMonitor(client.app.state.exam_store).ingest(None,ListingLink('SYNTHETIC rule fixture',url,CYCLE),FetchResult(url,url,('SYNTHETIC TEST. '+q).encode(),'text/plain',200),offline=True)
 payload=dict(cycle_id=CYCLE,notice_type='ORIGINAL',topics=['OTHER'],requires_rule_validation=True,facts=[dict(kind='RULE_CANDIDATE',page_number=1,literal_quote=q,date_value=None)])
 svc=SarvamService(client.app.state.exam_store,api_key='test-key',transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]})))
 svc.set_budget(5000);svc.record_credit_balance(59812)
 analysis=svc.process(notice.notice_id,0);assert analysis.status=='VALIDATED' and analysis.notice_changes
 return notice,analysis


def review_body(notice,operator):return dict(notice_id=notice.notice_id,reviewer_id=operator['user_id'],action='APPROVE',reason='Synthetic operator source review',reviewed_at=datetime.now(timezone.utc).isoformat(),expected_revision=1)


def test_publication_rechecks_values_and_rule_flag_atomically(client):
 store=client.app.state.exam_store;notice,analysis=analyze_fixture(client,'Minimum qualifying marks: 75%.')
 admin,operator=session(client,'operator');body=review_body(notice,operator)
 forged=analysis.model_dump(mode='json');forged['notice_changes'][0]['proposed_rule']['min_marks_percent']=1
 with store.connect(write=True) as con:con.execute('UPDATE v2_notice_analysis SET payload=? WHERE notice_id=?',(json.dumps(forged),notice.notice_id))
 response=client.post(f'/api/v2/admin/notices/{notice.notice_id}/review',headers=admin,json=body)
 assert response.status_code==409 and response.json()['code']=='RULE_PROPOSAL_NOT_VERIFIED'
 with store.connect(write=True) as con:
  con.execute('UPDATE v2_notice_analysis SET payload=? WHERE notice_id=?',(analysis.model_dump_json(),notice.notice_id))
  original=json.loads(con.execute('SELECT payload FROM v2_notices WHERE id=?',(notice.notice_id,)).fetchone()[0]);original['requires_rule_validation']=False
  con.execute('UPDATE v2_notices SET payload=? WHERE id=?',(json.dumps(original),notice.notice_id))
 response=client.post(f'/api/v2/admin/notices/{notice.notice_id}/review',headers=admin,json=body)
 assert response.status_code==409 and response.json()['code']=='RULE_VALIDATION_REQUIRED'
 with store.connect() as con:
  assert con.execute('SELECT count(*) FROM v2_rule_history').fetchone()[0]==0
  assert con.execute('SELECT count(*) FROM v2_updates').fetchone()[0]==0
  assert con.execute('SELECT count(*) FROM v2_reviews').fetchone()[0]==0
  assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==0


def test_second_prepared_notice_cannot_overwrite_new_rule_revision(client):
 first,_=analyze_fixture(client,'Minimum qualifying marks: 75%.')
 second,_=analyze_fixture(client,'Maximum annual household income: INR 29000.')
 admin,operator=session(client,'operator')
 assert client.post(f'/api/v2/admin/notices/{first.notice_id}/review',headers=admin,json=review_body(first,operator)).status_code==200
 response=client.post(f'/api/v2/admin/notices/{second.notice_id}/review',headers=admin,json=review_body(second,operator))
 assert response.status_code==409 and response.json()['code']=='STALE_RULE_REVISION'
 with client.app.state.exam_store.connect() as con:
  assert con.execute('SELECT count(*) FROM v2_updates').fetchone()[0]==1
  assert con.execute('SELECT count(*) FROM v2_rule_history').fetchone()[0]==1
