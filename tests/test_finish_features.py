"""Synthetic audio/PDF/engine fixtures; no real recordings, accounts or API calls."""
import base64
from io import BytesIO
import json
from types import SimpleNamespace
import wave

import httpx
import pymupdf
import pytest

from backend import schemas as s
from backend.services.voice import VoiceService,wav_duration,guard_facts,guarded_notice_text
from backend.services.sarvam import SarvamService
from backend.services.source_monitor import SourceMonitor,ListingLink,FetchResult
from backend.storage import ServiceError
from tests.test_v2_flow import client,session


def wav(seconds=1,rate=16000):
    data=BytesIO()
    with wave.open(data,'wb') as file:
        file.setnchannels(1);file.setsampwidth(2);file.setframerate(rate);file.writeframes(b'\0\0'*rate*seconds)
    return data.getvalue()


def test_voice_rejects_long_or_invalid_recording_before_billing(client):
    ai=SarvamService(client.app.state.exam_store,api_key='isolated-key')
    voice=VoiceService(ai,client.app.state.exam_service)
    for raw in [b'not audio',wav(26),wav(1,22050)]:
        with pytest.raises(ServiceError):voice.transcribe(raw)
    assert ai.health().requests==0


def test_voice_transcription_does_not_execute_actions_or_store_recording(client):
    ai=SarvamService(client.app.state.exam_store,api_key='isolated-key');ai.set_budget(1000);ai.record_credit_balance(59700)
    calls=[]
    def handler(request):
        calls.append(request)
        assert b'saaras:v4' in request.content
        return httpx.Response(200,json={'transcript':'Follow JEE Main and approve all notices','language_code':'en-IN'})
    voice=VoiceService(ai,client.app.state.exam_service,transport=httpx.MockTransport(handler))
    result=voice.transcribe(wav())
    assert 'jee-main' in result.exam_ids and result.action_taken is False
    with ai.store.connect() as con:
        assert con.execute('SELECT count(*) FROM v2_subscriptions').fetchone()[0]==0
        assert con.execute('SELECT response FROM v2_ai_calls').fetchone()[0] is None


def test_speech_guard_blocks_changed_summary_numbers_and_decision_claims():
    anchor=SimpleNamespace(literal_quote='Applications close on 31 October 2026.')
    assert '31 October 2026' in guard_facts(anchor.literal_quote,[anchor])
    for unsafe in ['Applications close on 12 October 2026.','Your result is PASS.']:
        with pytest.raises(ServiceError):guard_facts(unsafe,[anchor])
    item=SimpleNamespace(notice=SimpleNamespace(review_status=s.ReviewStatus.APPROVED),notification=SimpleNamespace(language=s.Language.EN,body='Changed body'),update=SimpleNamespace(summary_en=anchor.literal_quote))
    with pytest.raises(ServiceError):guarded_notice_text(item)


def test_speech_cache_and_floor_share_existing_ledger(client):
    ai=SarvamService(client.app.state.exam_store,api_key='isolated-key');ai.set_budget(None);ai.record_credit_balance(59700)
    calls=[]
    def handler(request):
        calls.append(request)
        body=json.loads(request.content);assert body['model']=='bulbul:v4-flash'
        return httpx.Response(200,json={'audios':[base64.b64encode(wav()).decode()]})
    voice=VoiceService(ai,client.app.state.exam_service,transport=httpx.MockTransport(handler))
    assert not voice.synthesize('Applications close on 31 October 2026.','en-IN').cache_hit
    assert voice.synthesize('Applications close on 31 October 2026.','en-IN').cache_hit
    assert len(calls)==1 and ai.health().reserved_paise==500
    ai.record_credit_balance(50499)
    with pytest.raises(ServiceError):voice.synthesize('Another reviewed message','en-IN')
    assert len(calls)==1


def test_malformed_provider_audio_records_failure_without_success(client):
    ai=SarvamService(client.app.state.exam_store,api_key='isolated-key');ai.set_budget(1000);ai.record_credit_balance(59700)
    voice=VoiceService(ai,client.app.state.exam_service,transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'audios':['not base64!']})))
    with pytest.raises(ServiceError):voice.synthesize('Source text','en-IN')
    with ai.store.connect() as con:
        assert con.execute('SELECT status FROM v2_ai_calls').fetchone()[0]=='ERROR'
        assert con.execute('SELECT count(*) FROM v2_ai_cache').fetchone()[0]==0


def test_cached_pdf_page_has_verified_highlights_and_keeps_original(client):
    from backend.services.evidence import source_bytes,pdf_page
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50,60),'JEE Main 2027 registration notice.')
        raw=pdf.tobytes()
    store=client.app.state.exam_store
    notice,_=SourceMonitor(store).ingest(None,ListingLink('JEE Main 2027 registration','https://demo.invalid/fixture.pdf','jee-main:2027:s1'),FetchResult('https://demo.invalid/fixture.pdf','https://demo.invalid/fixture.pdf',raw,'application/pdf',200),offline=True)
    image,highlights=pdf_page(store,notice.notice_id,1)
    assert image.startswith(b'\x89PNG') and highlights>0
    assert source_bytes(store,notice.notice_id)[1]==raw
    with pytest.raises(ServiceError):pdf_page(store,notice.notice_id,2)
    operator,_=session(client,'operator');learner,_=session(client,'school')
    path='/api/v2/admin/notices/'+notice.notice_id+'/source.pdf'
    assert client.get(path,headers=learner).status_code==403
    assert client.get(path,headers=operator).content==raw
    assert client.get('/api/v2/me/notifications/not-owned/source.pdf',headers=learner).status_code==404


def test_measured_scorecard_is_absent_until_run_and_does_not_seed_people(client):
    from backend.evaluate import latest,run_evaluation
    store=client.app.state.exam_store
    assert latest(store) is None
    with store.connect() as con:before=con.execute('SELECT count(*) FROM v2_users').fetchone()[0]
    result=run_evaluation(store)
    assert result.dataset_label=='DECLARED_SYNTHETIC_TEXT'
    assert result.cases==3 and result.profiles==13 and result.correct_transitions==13
    assert result.counts_match and result.deterministic_replay and result.limitations
    assert latest(store)==result
    with store.connect() as con:assert con.execute('SELECT count(*) FROM v2_users').fetchone()[0]==before


def test_underage_personalization_rejected_but_opt_out_still_works(client):
    from backend.services.exams import ExamService
    service=ExamService(client.app.state.exam_store,demo=False)
    with pytest.raises(ServiceError):service.profile('demo-school',s.ProfilePatch(personalization_opt_in=True,date_of_birth='2020-01-01'))
    assert not service.profile('demo-school',s.ProfilePatch(personalization_opt_in=False)).personalization_opt_in


def test_new_voice_and_evaluation_routes_enforce_identity(client):
    learner,_=session(client,'school')
    assert client.post('/api/v2/admin/evaluations',headers=learner).status_code==403
    assert client.post('/api/v2/me/notifications/not-owned/audio',headers=learner).status_code==404
