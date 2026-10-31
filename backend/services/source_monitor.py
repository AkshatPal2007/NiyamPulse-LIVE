"""Explicit individually tested official adapters, safe HTTP, immutable captures and polling.

No browser scraping, private endpoint guessing or protection bypass. All sources
start disabled. A real listing and mapped document extraction are required to enable one.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
from threading import Event,Thread
from urllib.parse import urljoin,urlsplit,urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import httpx
import pymupdf

from backend import schemas as s
from backend.services.pdf_intake import extract_pdf
from backend.storage import ServiceError,utc_text
from backend.services.exams import identifier
from backend.services.rule_engine import content_fingerprint

USER_AGENT="NiyamPulse/2.0 (low-frequency public exam-notice monitor)"
SUPPORTED_ADAPTERS={"nta-jee-main":"nta_jee_listing_v1","upsc-active":"upsc_active_v2","nta-neet-ug":"nta_neet_listing_v1"}


def canonical_url(url):
    parsed=urlsplit(url)
    return urlunsplit((parsed.scheme.lower(),parsed.netloc.lower(),parsed.path or "/",parsed.query,""))


def validate_public_url(url,allowed_hosts,*,resolve=True,resolver=None):
    parsed=urlsplit(url)
    if parsed.scheme.lower()!="https" or parsed.username or parsed.password or parsed.port not in {None,443} or parsed.hostname not in allowed_hosts:
        raise ServiceError(503,"SOURCE_URL_BLOCKED","Source URL is outside the exact HTTPS allowlist")
    if resolve:
        addresses=(resolver(parsed.hostname) if resolver else {r[4][0] for r in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ServiceError(503,"SOURCE_ADDRESS_BLOCKED","Private or non-public source addresses are blocked")
    return canonical_url(url)


@dataclass(frozen=True)
class FetchResult:
    requested_url:str
    final_url:str
    content:bytes
    content_type:str
    status:int


class SafeFetcher:
    def __init__(self,*,transport=None,resolver=None):
        self.transport,self.resolver=transport,resolver

    def get(self,url,allowed_hosts,*,max_bytes=10*1024*1024,allow_missing=False):
        requested=canonical_url(url)
        current=requested
        try:
            with httpx.Client(timeout=httpx.Timeout(20,connect=7),follow_redirects=False,trust_env=False,
                              headers={"User-Agent":USER_AGENT},transport=self.transport) as client:
                for _ in range(5):
                    validate_public_url(current,allowed_hosts,resolver=self.resolver)
                    with client.stream("GET",current) as response:
                        if response.status_code in {301,302,303,307,308}:
                            location=response.headers.get("location")
                            if not location: raise ServiceError(503,"SOURCE_REDIRECT_INVALID","Source redirect has no target")
                            current=canonical_url(urljoin(current,location));continue
                        if response.status_code in {404,410} and allow_missing:
                            return FetchResult(requested,current,b"","text/plain",response.status_code)
                        if response.status_code==429:
                            error=ServiceError(503,"SOURCE_RATE_LIMITED","Publisher returned 429; no immediate retry will run")
                            retry=response.headers.get("retry-after","")
                            if retry.isdigit(): error.retry_delay=min(int(retry),7*24*3600)
                            raise error
                        if response.status_code!=200:
                            raise ServiceError(503,"SOURCE_HTTP_ERROR",f"Publisher returned HTTP {response.status_code}")
                        content=bytearray()
                        for chunk in response.iter_bytes():
                            content.extend(chunk)
                            if len(content)>max_bytes: raise ServiceError(503,"SOURCE_TOO_LARGE","Source exceeds the bounded download limit")
                        content_type=response.headers.get("content-type","").split(";",1)[0].lower()
                        return FetchResult(requested,current,bytes(content),content_type,response.status_code)
                raise ServiceError(503,"SOURCE_REDIRECT_LIMIT","Source exceeded the redirect limit")
        except (httpx.HTTPError,OSError) as error:
            raise ServiceError(503,"SOURCE_UNAVAILABLE",f"Source fetch failed: {type(error).__name__}") from error

    def robots(self,url,allowed_hosts):
        parsed=urlsplit(url)
        robots_url=f"https://{parsed.netloc}/robots.txt"
        response=self.get(robots_url,allowed_hosts,max_bytes=128*1024,allow_missing=True)
        if response.status in {404,410}: return "ROBOTS_NOT_PROVIDED",None
        text=response.content.decode("utf-8",errors="replace")
        if "user-agent:" not in text.lower():
            if response.final_url.rstrip("/")==f"https://{parsed.netloc}" and response.content_type=="text/html":
                return "ROBOTS_REDIRECTS_TO_HOME_NO_DIRECTIVES",None
            raise ServiceError(503,"ROBOTS_UNCLEAR","Robots response is not a usable policy; source remains held")
        policy=RobotFileParser();policy.parse(text.splitlines())
        if not policy.can_fetch(USER_AGENT,url): raise ServiceError(503,"ROBOTS_DISALLOWED","Publisher robots policy disallows this path")
        return "ROBOTS_CHECKED_ALLOWED",policy.crawl_delay(USER_AGENT) or policy.crawl_delay("*")


@dataclass(frozen=True)
class ListingLink:
    title:str
    url:str
    cycle_id:str|None


def parse_listing(source,content):
    soup=BeautifulSoup(content,"html.parser")
    if source.source_id in {"nta-jee-main","nta-neet-ug"}:
        container=soup.select_one("#row-content")
        if container is None: raise ServiceError(503,"LISTING_STRUCTURE_CHANGED","NTA notice container was not found")
        anchors=container.select("a[href]")
    elif source.source_id=="upsc-active":
        container=soup.select_one(".view-exams .view-content")
        if container is None: raise ServiceError(503,"LISTING_STRUCTURE_CHANGED","UPSC examination container was not found")
        anchors=container.select(".views-field-field-exam-name a[href]")
    else: raise ServiceError(503,"ADAPTER_UNTESTED","No tested adapter exists for this source")
    links=[];seen=set()
    for anchor in anchors:
        title=" ".join(anchor.get_text(" ",strip=True).split())
        years=set(re.findall(r"\b(20\d{2})\b",title))
        year=next(iter(years)) if len(years)==1 else None
        cycle=None
        if source.source_id=="nta-neet-ug":
            if not re.search(r"NEET|National Eligibility cum Entrance",title,re.I):continue
            if re.search(r"list of toppers|individual results|qualified candidates",title,re.I):continue
            if year:cycle=f"neet-ug:{year}"
        elif source.source_id=="nta-jee-main":
            if not re.search(r"JEE|Joint Entrance Examination",title,re.I): continue
            sessions=set(re.findall(r"Session\s*[-:]?\s*([12])\b",title,re.I))
            session=next(iter(sessions)) if len(sessions)==1 else None
            if year and session: cycle=f"jee-main:{year}:s{session}"
        else:
            if re.search(r"Engineering Services",title,re.I):
                if year: cycle=f"upsc-ese:{year}"
            elif re.search(r"National Defence Academy.*Naval Academy",title,re.I):
                phase=re.search(r"Examination\s*\((II|I)\)",title,re.I)
                if year and phase: cycle=f"nda-na:{year}:{phase[1].lower()}"
            else: continue
        url=canonical_url(urljoin(str(source.listing_url),anchor.get("href","")))
        if not title or url in seen: continue
        validate_public_url(url,source.allowed_hosts,resolve=False)
        seen.add(url);links.append(ListingLink(title,url,cycle))
    if not links: raise ServiceError(503,"NO_LISTING_ITEMS","No examination notice links were recognized; review adapter structure")
    return links


def parse_attachments(source,parent,content):
    """Attachment ancestry is the observed exam detail page, never a guessed URL."""
    soup=BeautifulSoup(content,'html.parser')
    main=soup.select_one('.content-container,main,article')
    if main is None:raise ServiceError(503,'ATTACHMENT_STRUCTURE_CHANGED','Exam attachment region was not found')
    found=[];seen=set()
    for anchor in main.select('a[href]'):
        url=canonical_url(urljoin(parent.url,anchor['href']))
        if not urlsplit(url).path.lower().endswith('.pdf') or url in seen:continue
        validate_public_url(url,source.allowed_hosts,resolve=False)
        title=' '.join(anchor.get_text(' ',strip=True).split()) or 'Source PDF'
        found.append(ListingLink((parent.title+' · '+title)[:500],url,parent.cycle_id));seen.add(url)
    return found


def classify_title(title):
    text=title.lower()
    for pattern,kind,topic in [
        (r"admit.card|hall.ticket",s.NoticeType.ADMIT_CARD,s.Topic.ADMIT_CARD),
        (r"answer.key",s.NoticeType.ANSWER_KEY,s.Topic.ANSWER_KEY),
        (r"result|score.card",s.NoticeType.RESULT,s.Topic.RESULTS),
        (r"syllabus",s.NoticeType.SYLLABUS,s.Topic.SYLLABUS),
        (r"application|registration|last.date|deadline",s.NoticeType.INFORMATIONAL,s.Topic.REGISTRATION),
        (r"exam.*date|schedule",s.NoticeType.EXAM_DATE,s.Topic.EXAM_SCHEDULE),
    ]:
        if re.search(pattern,text): return kind,[topic]
    return s.NoticeType.INFORMATIONAL,[s.Topic.OTHER]


def extract_pages(content,content_type,document_id,*,allow_empty=False):
    digest=hashlib.sha256(content).hexdigest()
    if content.startswith(b"%PDF-") and content_type in {"application/pdf","application/octet-stream"}:
        # Keep the v1 twenty-page intake unchanged. Official v2 brochures can
        # be longer (the exercised UPSC ESE bulletin has 62 pages).
        with pymupdf.open(stream=content,filetype='pdf') as pdf:
            if pdf.needs_pass or not 1<=len(pdf)<=100:
                raise ServiceError(422,'SOURCE_PDF_PAGE_LIMIT','Official PDF must be readable and have at most 100 pages')
            if len(pdf)<=20:
                extraction=extract_pdf(content,document_id)
                pages=[p.text for p in extraction.pages];version=extraction.extractor_version
            else:
                pages=[];size=0
                for page in pdf:
                    text=page.get_text(sort=True);size+=len(text.encode('utf-8'))
                    if size>2*1024*1024:raise ServiceError(422,'SOURCE_TEXT_SIZE_LIMIT','Official embedded PDF text exceeds the bounded extraction size')
                    pages.append(text)
                version='pymupdf-100-pages-v1:'+pymupdf.VersionBind
    elif content_type in {"text/html","application/xhtml+xml","text/plain"}:
        if content_type=="text/plain": pages=[content.decode("utf-8")]
        else:
            soup=BeautifulSoup(content,"html.parser")
            for node in soup.select("script,style,nav,footer,form,noscript"): node.decompose()
            main=soup.select_one(".content-container,main,#row-content,article")
            if main is None: raise ServiceError(503,"NOTICE_STRUCTURE_CHANGED","No main notice content region was found")
            pages=[main.get_text("\n",strip=True)]
        version="html-main-text-v1"
    else: raise ServiceError(503,"NOTICE_TYPE_UNSUPPORTED","Notice response content type is unsupported")
    if not allow_empty and not any(p.strip() for p in pages): raise ServiceError(503,"OCR_REQUIRED","No embedded text; run explicit Sarvam Vision recovery")
    return pages,version,"extract-"+hashlib.sha256(f"{digest}:{version}".encode()).hexdigest()


class SourceMonitor:
    def __init__(self,store,*,fetcher=None,clock=None):
        self.store,self.fetcher=store,fetcher or SafeFetcher()
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def _snapshot(self,con,source_id,result,now):
        digest=hashlib.sha256(result.content).hexdigest()
        existing=con.execute("SELECT id FROM v2_snapshots WHERE source_id=? AND url=? AND sha256=?",(source_id,result.requested_url,digest)).fetchone()
        if existing: return existing[0]
        snapshot_id=identifier("snapshot")
        con.execute("INSERT INTO v2_snapshots VALUES (?,?,?,?,?,?,?)",(snapshot_id,source_id,result.requested_url,digest,result.content_type,result.content,utc_text(now)))
        return snapshot_id

    def ingest(self,source,link,document,*,listing=None,offline=False,parent=None,parent_document=None):
        now=self.clock();notice_id=identifier("notice")
        digest=hashlib.sha256(document.content).hexdigest()
        # Retain bounded original bytes even if the parser rejects the document.
        with self.store.connect(write=True) as con:self._snapshot(con,source.source_id if source else 'local-demo',document,now)
        pages,version,extraction_id=extract_pages(document.content,document.content_type,notice_id,allow_empty=True)
        has_text=any(p.strip() for p in pages)
        evidence=[]
        if has_text:
            page_number=next(i+1 for i,p in enumerate(pages) if p.strip())
            text=pages[page_number-1]
            quote=text.strip()[:1200]
            if len(quote)==1200 and "\n" in quote: quote=quote.rsplit("\n",1)[0]
            quote=quote.rstrip()
            start=text.index(quote)
            evidence=[s.EvidenceAnchor(document_id=notice_id,document_sha256=digest,page_number=page_number,literal_quote=quote,start_char=start,end_char=start+len(quote),extraction_id=extraction_id)]
        kind,topics=classify_title(link.title)
        from backend.services.sarvam import requires_rule_review
        needs_rules=requires_rule_review(link.title+"\n"+"\n".join(pages))
        notice=s.DetectedNotice(notice_id=notice_id,cycle_id=link.cycle_id,source_id=source.source_id if source else None,
                                source_kind=s.SourceKind.LOCAL_DEMO_FIXTURE if offline else s.SourceKind.OFFICIAL_WEB_LISTING,
                                title=link.title[:500],notice_type=kind,source_url=None if offline else document.final_url,document_sha256=digest,
                                first_seen_at=now,trust=s.DocumentTrust.UNVERIFIED if offline else s.DocumentTrust.MATCHED_CONFIGURED_SOURCE,
                                review_status=s.ReviewStatus.NEEDS_REVIEW,evidence=evidence,topics=topics,processing_mode="NEEDS_EXTRACTION" if not has_text else "OFFLINE_REPLAY" if offline else "SOURCE_EXCERPT",
                                requires_rule_validation=needs_rules,diagnostics=(["Rule validation is required before publication"] if needs_rules else [])+([] if has_text else ["No usable embedded text. Source retained; OCR and review are required before publication."]))
        source_key=source.source_id if source else "local-demo"
        meaningful_hash=content_fingerprint([link.cycle_id,link.title,version,pages])
        with self.store.connect(write=True) as con:
            document_snapshot=self._snapshot(con,source_key,document,now)
            old=con.execute("SELECT payload FROM v2_notices WHERE source_id=? AND canonical_url=? AND content_hash=?",(source_key,link.url,meaningful_hash)).fetchone()
            if old: return s.DetectedNotice.model_validate_json(old[0]),False
            listing_snapshot=self._snapshot(con,source_key,listing,now) if listing else None
            page_payload=json.dumps(pages,ensure_ascii=False,separators=(",",":"))
            con.execute("INSERT OR IGNORE INTO v2_extractions VALUES (?,?,?,?,?)",(extraction_id,document_snapshot,version,page_payload,hashlib.sha256(page_payload.encode()).hexdigest()))
            con.execute("INSERT INTO v2_notices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(notice_id,source_key,link.cycle_id,link.url,meaningful_hash,listing_snapshot,document_snapshot,page_payload,extraction_id,version,link.title,str(source.listing_url) if source else None,notice.model_dump_json()))
            if parent is not None:
                parent_snapshot=self._snapshot(con,source_key,parent_document,now)
                con.execute('INSERT INTO v2_attachment_lineage VALUES (?,?,?,?)',(notice_id,parent_snapshot,parent.url,parent.title))
            if not offline:
                con.execute("INSERT OR IGNORE INTO v2_processing_jobs(notice_id,status,next_attempt_at,updated_at) VALUES (?,'QUEUED',?,?)",(notice_id,utc_text(now),utc_text(now)))

        return notice,True

    def repair_legacy_excerpt(self,notice_id,expected_revision):
        """Repair only whitespace offsets in unreviewed, pre-analysis excerpts.

        Keep the same literal quote, bytes/hash, page and extraction. All other
        provenance checks run against the corrected anchor before it is saved.
        """
        from backend.services.exams import ExamService
        with self.store.connect(write=True) as con:
            row=con.execute('SELECT * FROM v2_notices WHERE id=?',(notice_id,)).fetchone()
            if row is None:raise ServiceError(404,'NOTICE_NOT_FOUND','Notice not found')
            notice=s.DetectedNotice.model_validate_json(row['payload'])
            if notice.revision!=expected_revision:raise ServiceError(409,'STALE_NOTICE_REVISION','Refresh before excerpt repair')
            if notice.processing_mode!='SOURCE_EXCERPT' or notice.review_status!=s.ReviewStatus.NEEDS_REVIEW or con.execute('SELECT 1 FROM v2_notice_analysis WHERE notice_id=?',(notice_id,)).fetchone():return notice
            pages=json.loads(row['pages']);fixed=[];changed=False
            for anchor in notice.evidence:
                if not 1<=anchor.page_number<=len(pages) or anchor.start_char is None or anchor.end_char is None:raise ServiceError(409,'EVIDENCE_MISMATCH','Excerpt bounds require manual source review')
                span=pages[anchor.page_number-1][anchor.start_char:anchor.end_char]
                if span==anchor.literal_quote:fixed.append(anchor);continue
                if span.strip()!=anchor.literal_quote:raise ServiceError(409,'EVIDENCE_MISMATCH','Excerpt differs beyond whitespace; repair refused')
                start=anchor.start_char+len(span)-len(span.lstrip())
                fixed.append(anchor.model_copy(update={'start_char':start,'end_char':start+len(anchor.literal_quote)}));changed=True
            if changed:
                notice.evidence=fixed
                ExamService(self.store)._verify_publication(con,row,notice,evidence_only=True)
                notice.revision+=1
                notice.diagnostics.append('Legacy source-excerpt whitespace bounds repaired against immutable text; source bytes and quote preserved.')
                con.execute('UPDATE v2_notices SET payload=? WHERE id=?',(notice.model_dump_json(),notice_id))
            return notice

    def rotating_batch(self,key,links,*,limit=5,advance=True):
        if not links:return []
        with self.store.connect(write=True) as con:
            row=con.execute('SELECT position FROM v2_source_cursors WHERE source_id=?',(key,)).fetchone()
            start=(row[0] if row else 0)%len(links)
            selected=(links[start:]+links[:start])[:limit]
            if advance:con.execute('INSERT OR REPLACE INTO v2_source_cursors VALUES (?,?)',(key,(start+len(selected))%len(links)))
        return selected

    def check(self,source_id,*,dry_run=True,enable=False):
        import uuid
        token=uuid.uuid4().hex;now=self.clock()
        with self.store.connect(write=True) as con:
            old=con.execute('SELECT lease_until FROM v2_source_leases WHERE source_id=?',(source_id,)).fetchone()
            if old and old[0]>utc_text(now):raise ServiceError(409,'SOURCE_CHECK_IN_PROGRESS','Another worker owns this source poll')
            con.execute('INSERT OR REPLACE INTO v2_source_leases VALUES (?,?,?)',(source_id,token,utc_text(now+timedelta(minutes=15))))
        try:return self._check(source_id,dry_run=dry_run,enable=enable)
        finally:
            with self.store.connect(write=True) as con:con.execute('DELETE FROM v2_source_leases WHERE source_id=? AND token=?',(source_id,token))

    def _check(self,source_id,*,dry_run=True,enable=False):
        if enable and dry_run:
            raise ServiceError(400,"ENABLE_REQUIRES_DISCOVERY","Enablement requires discovery and document extraction, not a dry run")
        source=next((i for i in self.store.sources() if i.source_id==source_id),None)
        if source is None: raise ServiceError(404,"SOURCE_NOT_FOUND","Source not found")
        now=self.clock()
        if source.enabled:
            with self.store.connect() as con:
                health=s.SourceHealth.model_validate_json(con.execute("SELECT health FROM v2_sources WHERE id=?",(source_id,)).fetchone()[0])
                if health.next_due_at and health.next_due_at>now:
                    raise ServiceError(429,"SOURCE_CHECK_NOT_DUE",f"Next source check is scheduled for {utc_text(health.next_due_at)}")
        result=s.MonitorCheckResult(source_id=source_id,checked_at=now,dry_run=dry_run,mode="LIVE")
        robots_status=None;status=None;delay=None
        try:
            if source_id not in SUPPORTED_ADAPTERS: raise ServiceError(503,"ADAPTER_UNTESTED","This source adapter has not been implemented or verified")
            robots_status,delay=self.fetcher.robots(str(source.listing_url),source.allowed_hosts)
            listing=self.fetcher.get(str(source.listing_url),source.allowed_hosts,max_bytes=4*1024*1024)
            status=listing.status
            if listing.content_type not in {"text/html","application/xhtml+xml"}: raise ServiceError(503,"LISTING_TYPE_INVALID","Listing did not return HTML")
            result.listing_sha256=hashlib.sha256(listing.content).hexdigest()
            links=parse_listing(source,listing.content)
            result.discovered_links=len(links)
            cycles={c.cycle_id for c in self.store.catalog().cycles}
            eligible=[link for link in links if link.cycle_id in cycles]
            result.unmapped=[f"{link.title}: exact configured year/session mapping unavailable" for link in links if link.cycle_id not in cycles]
            with self.store.connect(write=True) as con: self._snapshot(con,source_id,listing,now)
            usable=0
            for link in self.rotating_batch(source_id,eligible,advance=not dry_run):
                if dry_run: continue
                try:
                    if urlsplit(link.url).hostname!=urlsplit(str(source.listing_url)).hostname:
                        self.fetcher.robots(link.url,source.allowed_hosts)
                    document=self.fetcher.get(link.url,source.allowed_hosts)
                    notice,created=self.ingest(source,link,document,listing=listing)
                    if notice.processing_mode=="NEEDS_EXTRACTION":result.pending_extractions+=1
                    else:usable+=1
                    result.created_notices+=int(created);result.duplicates+=int(not created)
                    if source_id=='upsc-active' and document.content_type in {'text/html','application/xhtml+xml'}:
                        attachments=parse_attachments(source,link,document.content)
                        for child in self.rotating_batch(source_id+':'+hashlib.sha256(link.url.encode()).hexdigest(),attachments,limit=2):
                            self.fetcher.robots(child.url,source.allowed_hosts)
                            payload=self.fetcher.get(child.url,source.allowed_hosts)
                            attached,fresh=self.ingest(source,child,payload,listing=listing,parent=link,parent_document=document)
                            result.created_notices+=int(fresh);result.duplicates+=int(not fresh)
                            if attached.processing_mode=='NEEDS_EXTRACTION':result.pending_extractions+=1
                            else:usable+=1
                except (ServiceError,ValueError) as error:
                    delay=max(delay or 0,getattr(error,"retry_delay",0))
                    result.errors.append(str(error))
            if enable:
                if not eligible or result.errors or usable==0: raise ServiceError(503,"SOURCE_NOT_READY","A real mapped discovery without errors is required before enabling")
                source=s.OfficialSource.model_validate(source.model_dump(mode="json") | {"readiness":"ADAPTER_TESTED","adapter_name":SUPPORTED_ADAPTERS[source_id],"enabled":True})
        except (ServiceError,ValueError) as error:
            delay=max(delay or 0,getattr(error,"retry_delay",0))
            result.errors.append(str(error))
        with self.store.connect(write=True) as con:
            old=s.SourceHealth.model_validate_json(con.execute("SELECT health FROM v2_sources WHERE id=?",(source_id,)).fetchone()[0])
            health=s.SourceHealth(source_id=source_id,status="ERROR" if result.errors else "LIVE_OK",last_attempt_at=now,
                                  pending_extractions=result.pending_extractions,
                                  last_success_at=old.last_success_at if result.errors else now,last_error="; ".join(result.errors) or None,
                                  last_http_status=status,last_new_notices=result.created_notices,
                                  total_notices=con.execute("SELECT count(*) FROM v2_notices WHERE source_id=?",(source_id,)).fetchone()[0],robots_status=robots_status,
                                  next_due_at=now+timedelta(seconds=max(source.poll_interval_minutes*60,delay or 0)))
            con.execute("UPDATE v2_sources SET payload=?,health=? WHERE id=?",(source.model_dump_json(),health.model_dump_json(),source_id))
            con.execute("INSERT INTO v2_polls(source_id,checked_at,payload) VALUES (?,?,?)",(source_id,utc_text(now),result.model_dump_json()))
        return result

    def replay_demo(self):
        results=[]
        for cycle,title,text in [
            ("jee-main:2027:s1","JEE Main 2027 Session 1 · practice registration update","SYNTHETIC DEMO ONLY. This is a test registration announcement for JEE Main 2027 Session 1. It does not state a real application deadline."),
            ("gate:2027","GATE 2027 · practice exam schedule update","SYNTHETIC DEMO ONLY. This is a test exam schedule announcement for GATE 2027. It does not state an official examination date."),
        ]:
            url="https://demo.invalid/"+cycle.replace(":","-")
            document=FetchResult(url,url,text.encode(),"text/plain",200)
            item,_=self.ingest(None,ListingLink(title,url,cycle),document,offline=True)
            results.append(item)
        return results


class SourceScheduler:
    def __init__(self,monitor):
        self.monitor=monitor;self.stop_signal=Event()
        self.thread=Thread(target=self.run,daemon=True,name="niyampulse-v2-web-monitor")
    def start(self): self.thread.start()
    def stop(self):
        self.stop_signal.set();self.thread.join(timeout=30)
        if not self.thread.is_alive():
            with self.monitor.store.connect(write=True) as con: con.execute("DELETE FROM metadata WHERE key='v2_monitor_heartbeat'")
    def tick(self):
        now=self.monitor.clock()
        with self.monitor.store.connect(write=True) as con:
            con.execute("INSERT OR REPLACE INTO metadata VALUES ('v2_monitor_heartbeat',?)",(utc_text(now),))
            sources=self.monitor.store.sources(con)
        for source in sources:
            if self.stop_signal.is_set():break
            if not source.enabled:continue
            try:
                with self.monitor.store.connect() as con:
                    health=s.SourceHealth.model_validate_json(con.execute('SELECT health FROM v2_sources WHERE id=?',(source.source_id,)).fetchone()[0])
                if health.next_due_at is None or health.next_due_at<=now:self.monitor.check(source.source_id,dry_run=False)
            except Exception as error:
                import logging
                logging.getLogger(__name__).exception('Source worker isolated failure for %s',source.source_id)
                if isinstance(error,ServiceError) and error.code in {'SOURCE_CHECK_NOT_DUE','SOURCE_CHECK_IN_PROGRESS'}:continue
                health=s.SourceHealth(source_id=source.source_id,status='ERROR',last_attempt_at=now,last_error='Worker isolated failure: '+type(error).__name__,next_due_at=now+timedelta(minutes=1))
                with self.monitor.store.connect(write=True) as con:con.execute('UPDATE v2_sources SET health=? WHERE id=?',(health.model_dump_json(),source.source_id))

    def run(self):
        while not self.stop_signal.is_set():
            try:self.tick()
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Source scheduler tick failed; retrying next tick')
            self.stop_signal.wait(30)
