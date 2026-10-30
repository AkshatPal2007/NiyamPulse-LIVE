"""Synthetic PDF and mocked official SDK transport; no network or paid calls."""
import json
import httpx
import pymupdf
import pytest
from backend.services.sarvam import SarvamService
from backend.services.vision import VisionService,validated_pages
from backend.services.source_monitor import SourceMonitor,ListingLink,FetchResult
from backend.storage import ServiceError
from tests.test_v2_flow import client,session


def pdf_notice(client):
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50,50),'JEE Main 2027 registration notice.')
        raw=pdf.tobytes()
    item,_=SourceMonitor(client.app.state.exam_store).ingest(None,ListingLink('JEE Main 2027 registration','https://demo.invalid/ocr.pdf','jee-main:2027:s1'),FetchResult('https://demo.invalid/ocr.pdf','https://demo.invalid/ocr.pdf',raw,'application/pdf',200),offline=True)
    return item


def test_ocr_preserves_original_and_reuses_job_and_extraction(client):
    notice=pdf_notice(client);requests=[]
    def handler(request):
        requests.append(request.url.path)
        if request.method=='POST':return httpx.Response(201,json={'job_id':'test-job','status':'pending','run_id':'run-test'})
        base={'job_id':'test-job','status':'completed','usage':{'pages_total':1,'pages_processed':1,'pages_succeeded':1,'pages_failed':0}}
        if request.url.path.endswith('/status'):return httpx.Response(200,json=base|{'created_at':'2026-10-31T00:00:00Z','updated_at':'2026-10-31T00:00:01Z'})
        return httpx.Response(200,json=base|{'type':'parse','documents':[{'file_name':'notice.pdf','pages':[{'page_number':1,'content':'JEE Main 2027 registration notice.\nRecovered exact page.'}]}]})
    ai=SarvamService(client.app.state.exam_store,api_key='test-key');ai.set_budget(500)
    client.app.state.sarvam_service=ai
    client.app.state.vision_service=VisionService(ai,transport=httpx.MockTransport(handler),poll_seconds=0)
    admin,_=session(client,'operator');learner,_=session(client,'school')
    url='/api/v2/admin/notices/'+notice.notice_id+'/ocr'
    assert client.post(url,headers=learner,json={'expected_revision':0}).status_code==403
    result=client.post(url,headers=admin,json={'expected_revision':0})
    assert result.status_code==200,result.text
    assert result.json()['status']=='COMPLETED'
    detail=client.app.state.exam_service.notice_detail(notice.notice_id)
    assert detail.notice.document_sha256==notice.document_sha256
    assert detail.notice.revision==1 and detail.extraction_version.startswith('sarvam-vision')
    with ai.store.connect() as con:assert con.execute('SELECT count(*) FROM v2_extractions').fetchone()[0]==2
    assert client.post(url,headers=admin,json={'expected_revision':1}).json()['cache_hit']
    assert len(requests)==3 and ai.health().reserved_paise==500


def test_incomplete_and_duplicate_ocr_pages_are_rejected():
    for pages in [[],[{'page_number':2,'content':'Wrong page'}],[{'page_number':1,'content':''}]]:
        with pytest.raises(ValueError):validated_pages({'documents':[{'pages':pages}]},1)


def test_ocr_access_denial_preserves_notice_and_reservation(client):
    notice=pdf_notice(client)
    ai=SarvamService(client.app.state.exam_store,api_key='test-key');ai.set_budget(500)
    vision=VisionService(ai,transport=httpx.MockTransport(lambda _:httpx.Response(403,json={'error':'denied'})))
    with pytest.raises(ServiceError) as error:vision.process(notice.notice_id,0)
    assert error.value.code=='OCR_ACCESS_DENIED'
    assert client.app.state.exam_service.notice_detail(notice.notice_id).notice.revision==0
    assert ai.health().reserved_paise==500


def test_observed_doc_ai_block_schema_and_page_numbers():
    output={'documents':[{'pages':[{'page_num':1,'status':'completed','blocks':[{'reading_order':2,'text':'Second clause'},{'reading_order':1,'text':'First clause'}]}]}]}
    assert validated_pages(output,1)==['First clause\nSecond clause']


def test_ocr_table_markup_becomes_readable_immutable_text():
    output={'documents':[{'pages':[{'page_num':1,'status':'completed','blocks':[{'reading_order':1,'text':'<table><tr><td>Application window</td><td>24 October 2026 to 22 November 2026</td></tr></table>'}]}]}]}
    text=validated_pages(output,1)[0]
    assert '<td>' not in text and 'Application window' in text and '22 November 2026' in text


def test_no_text_pdf_is_retained_for_ocr_and_cannot_publish(client):
    with pymupdf.open() as pdf:pdf.new_page();raw=pdf.tobytes()
    notice,_=SourceMonitor(client.app.state.exam_store).ingest(None,ListingLink('JEE Main scanned notice','https://demo.invalid/blank.pdf','jee-main:2027:s1'),FetchResult('https://demo.invalid/blank.pdf','https://demo.invalid/blank.pdf',raw,'application/pdf',200),offline=True)
    assert notice.processing_mode=='NEEDS_EXTRACTION' and not notice.evidence
    admin,operator=session(client,'operator')
    result=client.post('/api/v2/admin/notices/'+notice.notice_id+'/review',headers=admin,json={'notice_id':notice.notice_id,'reviewer_id':operator['user_id'],'action':'APPROVE','reason':'Attempt synthetic unsupported blank publication','reviewed_at':'2026-10-31T00:00:00Z','expected_revision':0})
    assert result.status_code==409
