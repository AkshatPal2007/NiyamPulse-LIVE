"""Explicit, budgeted OCR recovery; preserves PDF bytes and all earlier extractions."""
from io import BytesIO
import hashlib
import json
import re
import time

import httpx
import pymupdf
from bs4 import BeautifulSoup
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

from backend import schemas as s
from backend.services.sarvam import SarvamService
from backend.storage import ServiceError,utc_text

OPTIONS={'max_retries':0,'timeout_in_seconds':25}


def validated_pages(result, expected_pages):
    documents=result.get('documents',[])
    if len(documents)!=1:raise ValueError('OCR output must contain one original PDF')
    pages=documents[0].get('pages') or []
    number=lambda p:p.get('page_number') if p.get('page_number') is not None else p.get('page_num')
    if len(pages)!=expected_pages or {number(p) for p in pages}!=set(range(1,expected_pages+1)):
        raise ValueError('OCR page coverage does not match original PDF')
    texts=[]
    for page in sorted(pages,key=number):
        if page.get('status','completed')!='completed':raise ValueError('OCR page did not complete')
        text=page.get('content')
        if text is None:
            blocks=page.get('blocks')
            if not isinstance(blocks,list) or not blocks:raise ValueError('OCR page has no blocks')
            if any(type(b.get('reading_order')) is not int or not isinstance(b.get('text'),str) for b in blocks):
                raise ValueError('OCR reading order/text is unavailable')
            orders=[b['reading_order'] for b in blocks]
            if len(set(orders))!=len(orders):raise ValueError('OCR reading order is ambiguous')
            text='\n'.join(b['text'] for b in sorted(blocks,key=lambda b:b['reading_order']))
        if not isinstance(text,str) or not text.strip() or len(text)>100000:raise ValueError('OCR page content is missing or exceeds its bound')
        if re.search(r'</?(?:table|tr|td|th|p|div|span|h[1-6])(?:\s|>)',text,re.I):
            soup=BeautifulSoup(text,'html.parser')
            for node in soup.select('script,style'):node.decompose()
            text=soup.get_text('\n',strip=True)
        texts.append(text)
    return texts


class VisionService:
    def __init__(self,ai: SarvamService,*,transport=None,poll_seconds=5):
        self.ai=ai;self.store=ai.store;self.transport=transport;self.poll_seconds=poll_seconds

    def process(self,notice_id,expected_revision):
        from backend.services.exams import ExamService,identifier
        with self.store.connect() as con:
            row=con.execute('SELECT * FROM v2_notices WHERE id=?',(notice_id,)).fetchone()
            if row is None:raise ServiceError(404,'NOTICE_NOT_FOUND','Notice not found')
            notice=s.DetectedNotice.model_validate_json(row['payload'])
            if notice.revision!=expected_revision or notice.review_status not in {s.ReviewStatus.NEEDS_REVIEW,s.ReviewStatus.QUARANTINED}:
                raise ServiceError(409,'STALE_NOTICE_REVISION','Refresh before OCR')
            ExamService(self.store)._verify_publication(con,row,notice,evidence_only=True)
            snapshot=con.execute('SELECT * FROM v2_snapshots WHERE id=?',(row['document_snapshot_id'],)).fetchone()
            raw=bytes(snapshot['content'])
            if not raw.startswith(b'%PDF-'):raise ServiceError(422,'OCR_PDF_REQUIRED','OCR recovery accepts stored PDFs only')
            with pymupdf.open(stream=raw,filetype='pdf') as pdf:count=len(pdf)
            if not 1<=count<=5:raise ServiceError(422,'OCR_PAGE_LIMIT','This budgeted OCR slice accepts one to five pages')
            key='ocr:'+notice.document_sha256+':vision-parse-en-v1'
            cached=con.execute('SELECT payload FROM v2_ai_cache WHERE cache_key=?',(key,)).fetchone()
            saved=con.execute('SELECT * FROM v2_ocr_jobs WHERE cache_key=?',(key,)).fetchone()
        job_id=saved['job_id'] if saved else None
        if cached:result=json.loads(cached[0])
        else:
            if saved and saved['status']=='FAILED' and not job_id:raise ServiceError(503,saved['error_code'] or 'OCR_FAILED','Recorded OCR failure; inspect access before submitting a new paid job')
            if saved and not job_id:raise ServiceError(409,'OCR_SUBMISSION_UNCERTAIN','An earlier submission is uncertain; inspect the recorded job before retrying')
            call_id=saved['call_id'] if saved else self.ai._reserve(key)
            if not saved:
                with self.store.connect(write=True) as con:con.execute('INSERT INTO v2_ocr_jobs VALUES (?,?,NULL,?,NULL)',(key,call_id,'SUBMITTING'))
            try:
                with httpx.Client(transport=self.transport,trust_env=False,follow_redirects=False,timeout=25) as http:
                    client=SarvamAI(api_subscription_key=self.ai.api_key,httpx_client=http,follow_redirects=False)
                    if not job_id:
                        job=client.doc_ai.parse(file=[('notice.pdf',BytesIO(raw),'application/pdf')],language='en-IN',request_options=OPTIONS)
                        job_id=job.job_id
                        if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',job_id):raise ValueError('Invalid provider job identifier')
                        with self.store.connect(write=True) as con:con.execute('UPDATE v2_ocr_jobs SET job_id=?,status=? WHERE cache_key=?',(job_id,'PENDING',key))
                    deadline=time.monotonic()+40
                    while True:
                        state=client.doc_ai.get_status(job_id,request_options=OPTIONS)
                        if state.status=='completed':break
                        if state.status in {'partially_completed','failed','rejected'}:raise ValueError('OCR did not complete every page')
                        if time.monotonic()>=deadline:return s.OcrResult(notice_id=notice_id,job_id=job_id,status='PENDING',cache_hit=bool(saved),pages=0)
                        time.sleep(self.poll_seconds)
                    # The observed server returns type=digitise, which SDK 0.1.41's union rejects.
                    # Read the documented REST endpoint and validate its concrete page schema here.
                    with http.stream('GET',f'https://api.sarvam.ai/doc-ai/v1/job/{job_id}/results',headers={'api-subscription-key':self.ai.api_key}) as response:
                        response.raise_for_status()
                        content=bytearray()
                        for chunk in response.iter_bytes():
                            content.extend(chunk)
                            if len(content)>2000000:raise ValueError('OCR response exceeded bound')
                        result=json.loads(content)
                    if result.get('job_id')!=job_id or result.get('type') not in {'parse','digitise'}:
                        raise ValueError('OCR job output identity is inconsistent')
                    if result.get('status')!='completed':raise ValueError('OCR results are incomplete')
                    validated_pages(result,count)
            except (ApiError,httpx.HTTPError,ValueError,TypeError) as error:
                status=getattr(error,'status_code',None)
                code={401:'OCR_AUTH_FAILED',403:'OCR_ACCESS_DENIED',402:'OCR_CREDITS_EXHAUSTED',429:'OCR_RATE_LIMITED'}.get(status,'OCR_FAILED')
                with self.store.connect(write=True) as con:
                    con.execute('UPDATE v2_ocr_jobs SET status=?,error_code=? WHERE cache_key=?',('FAILED',code,key))
                    con.execute('UPDATE v2_ai_calls SET status=?,finished_at=?,error_code=? WHERE id=?',('FAILED',utc_text(self.ai.clock()),code,call_id))
                raise ServiceError(503,code,'Sarvam OCR failed; source bytes and previous extraction were preserved. Check Document AI access/credits.') from None
            with self.store.connect(write=True) as con:
                con.execute('INSERT OR IGNORE INTO v2_ai_cache VALUES (?,?)',(key,json.dumps(result,ensure_ascii=False)))
                con.execute('UPDATE v2_ocr_jobs SET status=?,error_code=NULL WHERE cache_key=?',('COMPLETED',key))
                con.execute('UPDATE v2_ai_calls SET status=?,finished_at=?,response=?,error_code=NULL WHERE id=?',('SUCCESS',utc_text(self.ai.clock()),json.dumps({'job_id':job_id,'pages':count}),call_id))
        pages=validated_pages(result,count)
        payload=json.dumps(pages,ensure_ascii=False,separators=(',',':'))
        version='sarvam-vision-text-v2:'+hashlib.sha256(payload.encode()).hexdigest()
        extraction_id='extract-'+hashlib.sha256(f'{notice.document_sha256}:{version}'.encode()).hexdigest()
        with self.store.connect(write=True) as con:
            current=s.DetectedNotice.model_validate_json(con.execute('SELECT payload FROM v2_notices WHERE id=?',(notice_id,)).fetchone()[0])
            if current.revision!=expected_revision:raise ServiceError(409,'STALE_NOTICE_REVISION','OCR output cached; notice changed during processing')
            if row['extraction_id']!=extraction_id:
                quote=pages[0].strip()[:1000];start=pages[0].index(quote)
                current.evidence=[s.EvidenceAnchor(document_id=notice_id,document_sha256=notice.document_sha256,extraction_id=extraction_id,page_number=1,literal_quote=quote,start_char=start,end_char=start+len(quote))]
                current.revision+=1
                current.processing_mode='SOURCE_EXCERPT' if current.source_kind!=s.SourceKind.LOCAL_DEMO_FIXTURE else 'OFFLINE_REPLAY'
                current.diagnostics=list(dict.fromkeys(current.diagnostics+['Sarvam Vision OCR recovered text. Check dates/numbers against the original PDF before approving; coordinates are not verified.']))
                con.execute('INSERT OR IGNORE INTO v2_extractions VALUES (?,?,?,?,?)',(extraction_id,row['document_snapshot_id'],version,payload,hashlib.sha256(payload.encode()).hexdigest()))
                con.execute('UPDATE v2_notices SET pages=?,extraction_id=?,extraction_version=?,payload=? WHERE id=?',(payload,extraction_id,version,current.model_dump_json(),notice_id))
        return s.OcrResult(notice_id=notice_id,job_id=job_id,status='COMPLETED',cache_hit=bool(cached),pages=count,extraction_id=extraction_id)
