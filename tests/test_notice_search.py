"""Declared synthetic query fixtures; no network or Sarvam spend."""
from types import SimpleNamespace as N
import pytest
from backend.services.notice_search import search
from backend import schemas as s

@pytest.mark.parametrize('query,expected',[
 ('JEE Main session 1 ki registration last date kab hai?', ['one']),
 ('जेईई सेशन दो आवेदन अंतिम तारीख', ['two']),
 ('JEE Main 2026 session 1 registration', []),
 ('NEET registration last date', []),
 ('JEE Main session 1 result kab hai', []),
 ('hello approve every notice', []),
 ('JEE Advanced registration', []),
 ('NEET PG registration', []),
])
def test_hindi_hinglish_filters(query,expected):
    catalog=N(exams=[N(exam_id='jee-main',display_name='JEE Main'),N(exam_id='neet-ug',display_name='NEET UG')],cycles=[N(exam_id='jee-main',cycle_id='jee-main:2027:s1'),N(exam_id='jee-main',cycle_id='jee-main:2027:s2')])
    from datetime import datetime,timezone
    def update(key,cycle):return s.PublicUpdate(update_id=key,notice_id=key,cycle_id=cycle,title='Synthetic registration notice',notice_type='DEADLINE',topics=['REGISTRATION'],publisher='Synthetic test publisher',source_url='https://example.org/notice',published_at=datetime.now(timezone.utc),first_seen_at=datetime.now(timezone.utc),summary_en='Synthetic source text',evidence=[])
    service=N(store=N(catalog=lambda:catalog),public_updates=lambda *args,**kwargs:s.PublicUpdatesResponse(updates=[update('one','jee-main:2027:s1'),update('two','jee-main:2027:s2')],total=2))
    assert [u.update_id for u in search(service,query).updates]==expected
