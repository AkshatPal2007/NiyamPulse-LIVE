"""Durable bounded extraction queue. Never reviews, applies rules or delivers alerts."""
from datetime import datetime,timedelta,timezone
import json
import logging
from threading import Event,Thread
import uuid

from backend import schemas as s
from backend.storage import ServiceError,utc_text


class ProcessingService:
    def __init__(self,ai,vision,*,clock=None):
        self.ai,self.vision,self.store=ai,vision,ai.store
        self.clock=clock or ai.clock

    def enqueue_pending(self):
        now=utc_text(self.clock())
        with self.store.connect(write=True) as con:
            for row in con.execute('SELECT id,payload FROM v2_notices').fetchall():
                notice=s.DetectedNotice.model_validate_json(row['payload'])
                if notice.review_status!=s.ReviewStatus.NEEDS_REVIEW:
                    con.execute("UPDATE v2_processing_jobs SET status='COMPLETE',lease_until=NULL,last_error=NULL,updated_at=? WHERE notice_id=? AND status!='COMPLETE'",(now,notice.notice_id))
                    con.execute('DELETE FROM v2_processing_leases WHERE notice_id=?',(notice.notice_id,))
                    continue
                if notice.source_kind==s.SourceKind.LOCAL_DEMO_FIXTURE:continue
                con.execute("INSERT OR IGNORE INTO v2_processing_jobs(notice_id,status,next_attempt_at,updated_at) VALUES (?,'QUEUED',?,?)",(notice.notice_id,now,now))
            if self.ai._credit_safety(con,con.execute('SELECT coalesce(sum(reserved_paise),0) FROM v2_ai_calls').fetchone()[0],con.execute('SELECT limit_paise FROM v2_ai_budget WHERE id=1').fetchone()[0]).paid_requests_allowed:
                con.execute("UPDATE v2_processing_jobs SET status='QUEUED',next_attempt_at=? WHERE status='PAUSED' AND last_error IN ('SARVAM_CREDIT_RESERVE_PROTECTED','SARVAM_NOT_CONFIGURED','SARVAM_BUDGET_EXCEEDED','SARVAM_CREDITS_EXHAUSTED') AND attempts<3",(now,))

    def claim(self):
        now=self.clock();token=uuid.uuid4().hex
        with self.store.connect(write=True) as con:
            # A lost lease is uncertain work. Operator must reconcile it; do not
            # silently resubmit a paid call whose response may have been lost.
            con.execute("UPDATE v2_processing_jobs SET status='PAUSED',last_error='WORKER_LEASE_EXPIRED',lease_until=NULL,updated_at=? WHERE status='LEASED' AND lease_until<=?",(utc_text(now),utc_text(now)))
            con.execute("DELETE FROM v2_processing_leases WHERE notice_id IN (SELECT notice_id FROM v2_processing_jobs WHERE status!='LEASED')")
            row=con.execute("SELECT * FROM v2_processing_jobs WHERE status IN ('QUEUED','RETRY') AND next_attempt_at<=? AND attempts<3 ORDER BY next_attempt_at,notice_id LIMIT 1",(utc_text(now),)).fetchone()
            if row is None:return None
            lease=utc_text(now+timedelta(minutes=5))
            con.execute("UPDATE v2_processing_jobs SET status='LEASED',lease_until=?,updated_at=? WHERE notice_id=?",(lease,utc_text(now),row['notice_id']))
            con.execute('INSERT OR REPLACE INTO v2_processing_leases VALUES (?,?)',(row['notice_id'],token))
            return row['notice_id'],token

    def finish(self,notice_id,token,status,error=None,*,count_attempt=True,retry_seconds=60):
        now=self.clock()
        with self.store.connect(write=True) as con:
            owned=con.execute('SELECT token FROM v2_processing_leases WHERE notice_id=?',(notice_id,)).fetchone()
            job=con.execute('SELECT * FROM v2_processing_jobs WHERE notice_id=?',(notice_id,)).fetchone()
            if owned is None or owned[0]!=token or job['status']!='LEASED' or job['lease_until']<=utc_text(now):return False
            if status=='RETRY' and job['attempts']+int(count_attempt)>=3:status='HELD'
            con.execute('UPDATE v2_processing_jobs SET status=?,attempts=attempts+?,next_attempt_at=?,lease_until=NULL,last_error=?,updated_at=? WHERE notice_id=?',(status,int(count_attempt),utc_text(now+timedelta(seconds=retry_seconds)),error,utc_text(now),notice_id))
            con.execute('DELETE FROM v2_processing_leases WHERE notice_id=? AND token=?',(notice_id,token))
        return True

    def tick(self):
        self.enqueue_pending()
        claimed=self.claim()
        if claimed is None:return False
        notice_id,token=claimed
        try:
            with self.store.connect() as con:
                notice=s.DetectedNotice.model_validate_json(con.execute('SELECT payload FROM v2_notices WHERE id=?',(notice_id,)).fetchone()[0])
            if notice.review_status!=s.ReviewStatus.NEEDS_REVIEW:
                self.finish(notice_id,token,'COMPLETE',count_attempt=False);return True
            if notice.processing_mode=='SOURCE_EXCERPT':
                from backend.services.source_monitor import SourceMonitor
                notice=SourceMonitor(self.store).repair_legacy_excerpt(notice_id,notice.revision)
            if notice.processing_mode=='NEEDS_EXTRACTION':
                result=self.vision.process(notice_id,notice.revision)
                if result.status=='PENDING':
                    self.finish(notice_id,token,'RETRY','OCR_PENDING');return True
                with self.store.connect() as con:notice=s.DetectedNotice.model_validate_json(con.execute('SELECT payload FROM v2_notices WHERE id=?',(notice_id,)).fetchone()[0])
            analysis=self.ai.process(notice_id,notice.revision)
            status='REVIEW_READY' if analysis.status=='VALIDATED' and (not notice.requires_rule_validation or bool(analysis.notice_changes)) else 'HELD'
            # The deterministic gate can update the notice classification during extraction.
            with self.store.connect() as con:notice=s.DetectedNotice.model_validate_json(con.execute('SELECT payload FROM v2_notices WHERE id=?',(notice_id,)).fetchone()[0])
            if notice.requires_rule_validation and not analysis.notice_changes:status='HELD'
            self.finish(notice_id,token,status,'SOURCE_REVIEW_REQUIRED' if status=='HELD' else None)
        except ServiceError as error:
            paused={'SARVAM_CREDIT_RESERVE_PROTECTED','SARVAM_NOT_CONFIGURED','SARVAM_BUDGET_EXCEEDED','SARVAM_CREDITS_EXHAUSTED','SARVAM_AUTH_FAILED','SARVAM_UNAVAILABLE','VISION_UNAVAILABLE','OCR_UNCERTAIN_SUBMISSION'}
            with self.store.connect() as con:attempts=con.execute('SELECT attempts FROM v2_processing_jobs WHERE notice_id=?',(notice_id,)).fetchone()[0]
            retry=error.code in {'SARVAM_RATE_LIMITED','STALE_NOTICE_REVISION','ANALYSIS_IN_PROGRESS','ANALYSIS_CACHE_READY'} and attempts<2
            state='PAUSED' if error.code in paused else 'RETRY' if retry else 'HELD'
            admission_paused=error.code in {'SARVAM_CREDIT_RESERVE_PROTECTED','SARVAM_NOT_CONFIGURED','SARVAM_BUDGET_EXCEEDED'}
            self.finish(notice_id,token,state,error.code,count_attempt=not admission_paused,retry_seconds=max(60*2**attempts,getattr(error,'retry_delay',0)))
        except Exception:
            logging.getLogger(__name__).exception('Processing isolated failure for %s',notice_id)
            self.finish(notice_id,token,'PAUSED','PROCESSING_UNCERTAIN_FAILURE')
        return True

    def queue(self):
        now=self.clock()
        with self.store.connect() as con:
            jobs=[s.ProcessingJob.model_validate(dict(row)) for row in con.execute('SELECT * FROM v2_processing_jobs ORDER BY updated_at DESC LIMIT 200')]
            counts={r[0]:r[1] for r in con.execute('SELECT status,count(*) FROM v2_processing_jobs GROUP BY status')}
            heartbeat=con.execute("SELECT value FROM metadata WHERE key='v2_processing_heartbeat'").fetchone()
        active=heartbeat is not None and timedelta(0)<=now-datetime.fromisoformat(heartbeat[0].replace('Z','+00:00'))<timedelta(seconds=90)
        return s.ProcessingQueue(jobs=jobs,counts=counts,worker_active=active)

    def retry(self,notice_id):
        with self.store.connect(write=True) as con:
            row=con.execute('SELECT * FROM v2_processing_jobs WHERE notice_id=?',(notice_id,)).fetchone()
            if row is None:raise ServiceError(404,'PROCESSING_JOB_NOT_FOUND','No processing job exists')
            if row['status']=='LEASED':raise ServiceError(409,'PROCESSING_IN_PROGRESS','Worker owns the current job')
            if row['attempts']>=3:raise ServiceError(409,'PROCESSING_RETRY_LIMIT','Bounded attempts exhausted; inspect source and retained results')
            con.execute("UPDATE v2_processing_jobs SET status='QUEUED',next_attempt_at=?,last_error=NULL,updated_at=? WHERE notice_id=?",(utc_text(self.clock()),utc_text(self.clock()),notice_id))
            result=s.ProcessingJob.model_validate(dict(con.execute('SELECT * FROM v2_processing_jobs WHERE notice_id=?',(notice_id,)).fetchone()))
        return result


class ProcessingScheduler:
    def __init__(self,service):
        self.service=service;self.stop_signal=Event()
        self.thread=Thread(target=self.run,daemon=True,name='niyampulse-v2-processing')
    def start(self):self.thread.start()
    def stop(self):
        self.stop_signal.set();self.thread.join(timeout=5)
        if not self.thread.is_alive():
            with self.service.store.connect(write=True) as con:con.execute("DELETE FROM metadata WHERE key='v2_processing_heartbeat'")
    def run(self):
        while not self.stop_signal.is_set():
            try:
                with self.service.store.connect(write=True) as con:con.execute("INSERT OR REPLACE INTO metadata VALUES ('v2_processing_heartbeat',?)",(utc_text(self.service.clock()),))
                self.service.tick()
            except Exception:logging.getLogger(__name__).exception('Processing worker tick failed; retrying next tick')
            self.stop_signal.wait(10)
