"""Deterministic Hindi/Hinglish filters over approved official source updates only."""
import re
from backend import schemas as s

ALIASES={'jee-main':r'jee(?!\s+advanced)(?: main)?|जेईई(?!\s+एडवांस)|जे इ इ','neet-ug':r'neet(?!\s+pg)|नीट(?!\s+पीजी)','nda-na':r'nda|एनडीए','gate':r'gate|गेट','upsc-ese':r'ese|engineering services|ईएसई','ssc-je':r'ssc je|एसएससी जेई'}

def search(exams,query='',cycle_id=None):
    text=query.lower()
    catalog=exams.store.catalog()
    ids={e.exam_id for e in catalog.exams if re.search(r'(?<!\w)(?:'+ALIASES.get(e.exam_id,re.escape(e.display_name.lower()))+r')(?!\w)',text)}
    years=re.findall(r'\b20\d{2}\b',text)
    session=re.search(r'(?:session|सत्र|सेशन)[\s:-]*(1|2|one|two|एक|दो)',text)
    session_id={'one':'1','two':'2','एक':'1','दो':'2'}.get(session[1],session[1]) if session else None
    cycles={c.cycle_id for c in catalog.cycles if (not cycle_id or c.cycle_id==cycle_id) and (not ids or c.exam_id in ids) and (not years or any(y in c.cycle_id for y in years)) and (not session_id or c.cycle_id.endswith(':s'+session_id))}
    intents=[]
    for topic,pattern in [('REGISTRATION',r'registr|apply|application|last date|deadline|पंजीकरण|आवेदन|आखिरी|अंतिम'),('EXAM_SCHEDULE',r'exam date|exam kab|परीक्षा|schedule|परीक्षा कब'),('ADMIT_CARD',r'admit|एडमिट'),('RESULTS',r'result|रिजल्ट|परिणाम')]:
        if re.search(pattern,text):intents.append(topic)
    if not cycle_id and not ids:return s.PublicUpdatesResponse(total=0)
    items=[u for u in exams.public_updates(cycle_id,limit=100000).updates if u.cycle_id in cycles and (not intents or any(t.value in intents for t in u.topics))]
    if cycle_id:items.sort(key=lambda u:not any(t.value in {'REGISTRATION','EXAM_SCHEDULE'} for t in u.topics))
    return s.PublicUpdatesResponse(updates=items[:100],total=len(items))
