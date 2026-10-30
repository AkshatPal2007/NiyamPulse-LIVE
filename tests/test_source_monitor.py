"""Captured official HTML and mocked HTTP; these tests make no live requests."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from backend.exam_store import ExamStore
from backend.services.source_monitor import SafeFetcher,SourceMonitor,parse_listing,validate_public_url
from backend.storage import ServiceError
from backend.tests.local_temp import LocalTemporaryDirectory

ROOT=Path(__file__).parent/"fixtures/official"


@pytest.fixture
def store():
    temp=LocalTemporaryDirectory()
    result=ExamStore(Path(temp.name)/"app.sqlite3")
    yield result
    temp.cleanup()


def test_two_captured_official_publishers_and_exact_cycle_routing(store):
    manifest=json.loads((ROOT/"capture_manifest.json").read_text(encoding="utf-8"))
    sources={s.source_id:s for s in store.sources()}
    for source_id,name,cycle in [("nta-jee-main","nta-listing","jee-main:2027:s1"),("upsc-active","upsc-listing","upsc-ese:2027")]:
        data=(ROOT/(name+".html")).read_bytes()
        assert hashlib.sha256(data).hexdigest()==manifest[name]["sha256"]
        links=parse_listing(sources[source_id],data)
        assert any(link.cycle_id==cycle for link in links)
        assert all(not link.cycle_id or "2026" in link.cycle_id or "2027" in link.cycle_id or "2025" in link.cycle_id for link in links)


def test_redirect_private_network_and_download_limits():
    for url in ["http://jeemain.nta.nic.in/", "https://user:pass@jeemain.nta.nic.in/", "https://evil.example/", "https://jeemain.nta.nic.in:444/"]:
        with pytest.raises(ServiceError):validate_public_url(url,["jeemain.nta.nic.in"],resolve=False)
    with pytest.raises(ServiceError): validate_public_url("https://jeemain.nta.nic.in/",["jeemain.nta.nic.in"],resolver=lambda _:['127.0.0.1'])
    redirects=SafeFetcher(transport=httpx.MockTransport(lambda _:httpx.Response(302,headers={'location':'https://127.0.0.1/private'})),resolver=lambda _:['93.184.216.34'])
    with pytest.raises(ServiceError):redirects.get("https://jeemain.nta.nic.in/",["jeemain.nta.nic.in"])
    large=SafeFetcher(transport=httpx.MockTransport(lambda _:httpx.Response(200,content=b'x'*200)),resolver=lambda _:['93.184.216.34'])
    with pytest.raises(ServiceError):large.get("https://jeemain.nta.nic.in/",["jeemain.nta.nic.in"],max_bytes=100)


def mock_fetcher(*,changed=False,listing_status=200,disallow=False):
    def response(request):
        if request.url.path=="/robots.txt":return httpx.Response(200,headers={'content-type':'text/plain'},text='User-agent: *\nDisallow: /' if disallow else 'User-agent: *\nAllow: /')
        if request.url.host=='jeemain.nta.nic.in':return httpx.Response(listing_status,headers={'content-type':'text/html'},content=(ROOT/'nta-listing.html').read_bytes())
        text='National Testing Agency\nJEE Main 2027 Session 1\nSYNTHETIC TEST notice registration '+('changed' if changed else 'original')
        return httpx.Response(200,headers={'content-type':'text/html'},text='<main>'+text+'</main>')
    return SafeFetcher(transport=httpx.MockTransport(response),resolver=lambda _:['93.184.216.34'])


def test_dry_run_dedup_changed_content_and_genuine_health_fields(store):
    clock=lambda:datetime(2026,10,30,tzinfo=timezone.utc)
    monitor=SourceMonitor(store,fetcher=mock_fetcher(),clock=clock)
    dry=monitor.check('nta-jee-main',dry_run=True)
    assert dry.discovered_links>=1 and dry.created_notices==0
    result=monitor.check('nta-jee-main',dry_run=False)
    assert result.created_notices==1 and not result.errors
    assert monitor.check('nta-jee-main',dry_run=False).duplicates==1
    changed=SourceMonitor(store,fetcher=mock_fetcher(changed=True),clock=clock).check('nta-jee-main',dry_run=False)
    assert changed.created_notices==1
    with store.connect() as con:
        assert con.execute('SELECT count(*) FROM v2_notices').fetchone()[0]==2
        assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==0
        health=json.loads(con.execute("SELECT health FROM v2_sources WHERE id='nta-jee-main'").fetchone()[0])
        assert health['status']=='LIVE_OK' and health['last_success_at'] and health['total_notices']==2


def test_changed_markup_timeout_rate_limit_and_robots_fail_closed(store):
    with pytest.raises(ServiceError):parse_listing(next(i for i in store.sources() if i.source_id=='nta-jee-main'),b'<html>No notice region</html>')
    for fetcher in [mock_fetcher(listing_status=429),mock_fetcher(disallow=True),SafeFetcher(transport=httpx.MockTransport(lambda _:(_ for _ in ()).throw(httpx.ReadTimeout('test timeout'))),resolver=lambda _:['93.184.216.34'])]:
        result=SourceMonitor(store,fetcher=fetcher).check('nta-jee-main',dry_run=False,enable=True)
        assert result.errors
        assert not next(s for s in store.sources() if s.source_id=='nta-jee-main').enabled
    with store.connect() as con:
        assert con.execute('SELECT count(*) FROM v2_notices').fetchone()[0]==0


def test_dynamic_page_footer_does_not_create_duplicate_alerts(store):
    from backend.services.source_monitor import FetchResult,ListingLink
    source=next(i for i in store.sources() if i.source_id=='nta-jee-main')
    link=ListingLink('JEE Main 2027 Session 1 registration','https://jeemain.nta.nic.in/notice','jee-main:2027:s1')
    monitor=SourceMonitor(store)
    for counter in [1,2]:
        content=f'<main>National Testing Agency JEE Main 2027 Session 1 registration notice.</main><footer>Visitors: {counter}</footer>'.encode()
        _,created=monitor.ingest(source,link,FetchResult(link.url,link.url,content,'text/html',200),listing=None)
        assert created==(counter==1)


def test_dry_run_cannot_enable_source_without_document_extraction(store):
    monitor=SourceMonitor(store,fetcher=mock_fetcher())
    with pytest.raises(ServiceError) as error:
        monitor.check('nta-jee-main',dry_run=True,enable=True)
    assert error.value.code=='ENABLE_REQUIRES_DISCOVERY'
    assert not next(s for s in store.sources() if s.source_id=='nta-jee-main').enabled
