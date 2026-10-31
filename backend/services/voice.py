"""Bounded source-backed speech. Transcripts search; never execute account actions."""
import base64
import hashlib
from io import BytesIO
import re
import wave
import httpx

from backend import schemas as s
from backend.storage import ServiceError, utc_text


def wav_duration(raw, *, upload=False):
    if not 44 <= len(raw) <= (1024*1024 if upload else 8*1024*1024):
        raise ServiceError(422,'VOICE_SIZE','Audio exceeds the bounded WAV size')
    try:
        with wave.open(BytesIO(raw),'rb') as audio:
            duration=audio.getnframes()/audio.getframerate()
            if audio.getcomptype()!='NONE' or audio.getnchannels() not in (1,2) or not audio.getnframes():raise ValueError()
            if upload and (duration>25 or audio.getnchannels()!=1 or audio.getsampwidth()!=2 or audio.getframerate()!=16000):raise ValueError()
            if not upload and duration>180:raise ValueError()
            if len(audio.readframes(audio.getnframes())) != audio.getnframes()*audio.getnchannels()*audio.getsampwidth():raise ValueError()
            return duration
    except (wave.Error,EOFError,ValueError,ZeroDivisionError):
        raise ServiceError(422,'VOICE_FORMAT','Use a nonempty mono 16 kHz PCM WAV, up to 25 seconds') from None


def guarded_notice_text(item):
    if item.notice.review_status!=s.ReviewStatus.APPROVED:
        raise ServiceError(409,'VOICE_REVIEW_REQUIRED','Speech requires a reviewed notice')
    expected=item.update.summary_hi if item.notification.language==s.Language.HI else item.update.summary_en
    body=item.notification.body
    if not expected or body!=expected[:1600]:
        raise ServiceError(409,'VOICE_FACT_GUARD','Stored notification differs from the reviewed summary')
    return guard_facts(body,item.update.evidence)


def guard_facts(body,anchors):
    evidence='\n'.join(anchor.literal_quote for anchor in anchors)
    numbers=lambda text:set(re.findall(r'\d+(?:[.,:/-]\d+)*',text))
    if not numbers(body).issubset(numbers(evidence)):
        raise ServiceError(409,'VOICE_FACT_GUARD','A number or date has no literal source support')
    if re.search(r'\b(PASS|FAIL|UNKNOWN|CONFLICT|eligible|approved for admission)\b',body,re.I):
        raise ServiceError(409,'VOICE_FACT_GUARD','Decision assertions are not admitted to informational speech')
    return body+'\n'+s.DISCLAIMER


class VoiceService:
    def __init__(self,ai,exams,*,transport=None):self.ai,self.exams,self.transport=ai,exams,transport

    def request(self,key,endpoint,*,data=None,files=None,payload=None,validate=None,cache=None):
        call=self.ai._reserve(key)
        code=None
        try:
            with httpx.Client(transport=self.transport,timeout=25,follow_redirects=False) as client:
                response=client.post('https://api.sarvam.ai/'+endpoint,headers={'api-subscription-key':self.ai.api_key},data=data,files=files,json=payload)
            if response.status_code!=200:
                code={401:'SARVAM_AUTH_FAILED',402:'SARVAM_CREDITS_EXHAUSTED',429:'SARVAM_RATE_LIMITED'}.get(response.status_code,'VOICE_PROVIDER_FAILED')
                raise ValueError()
            result=response.json()
            if validate:validate(result)
        except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError,AttributeError,ServiceError):
            code=code or 'VOICE_PROVIDER_FAILED'
            with self.ai.store.connect(write=True) as con:
                con.execute('UPDATE v2_ai_calls SET status=?,finished_at=?,error_code=? WHERE id=?',('ERROR',utc_text(self.ai.clock()),code,call))
            raise ServiceError(503,code,'Speech request failed; reservation retained, no automatic retry') from None
        # No recording, transcript or provider response goes into the financial log.
        with self.ai.store.connect(write=True) as con:
            con.execute('UPDATE v2_ai_calls SET status=?,finished_at=? WHERE id=?',('SUCCESS',utc_text(self.ai.clock()),call))
            if cache:con.execute('INSERT OR IGNORE INTO v2_ai_cache VALUES (?,?)',(key,cache(result).model_dump_json()))
        return result

    def transcribe(self,raw):
        wav_duration(raw,upload=True)
        key='voice-input-'+hashlib.sha256(raw).hexdigest()
        result=self.request(key,'speech-to-text',data={'model':'saaras:v4','mode':'transcribe','language_code':'unknown'},files={'file':('query.wav',raw,'audio/wav')},validate=validate_transcript)
        text=result.get('transcript');language=result.get('language_code','unknown')
        if not isinstance(text,str) or not 0<len(text.strip())<=4000:raise ServiceError(503,'VOICE_RESPONSE_INVALID','No usable transcript was returned')
        # Only suggest literal catalog-name matches. The user confirms a search/follow.
        aliases={'jee-main':['jee','जेईई'],'neet-ug':['neet','नीट'],'gate':['gate','गेट'],'nda':['nda','एनडीए']}
        matches=[]
        for exam in self.ai.store.catalog().exams:
            names=[exam.display_name,*aliases.get(exam.exam_id,[])]
            if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text,re.I) for name in names):matches.append(exam.exam_id)
        return s.VoiceSearchResult(transcript=text.strip(),language_code=str(language),exam_ids=matches)

    def speak(self,user_id,notification_id):
        item=self.exams.notification(user_id,notification_id)
        text=guarded_notice_text(item)
        language='hi-IN' if item.notification.language==s.Language.HI else 'en-IN'
        return self.synthesize(text,language)

    def preview(self,notice_id):
        detail=self.exams.notice_detail(notice_id)
        if detail.notice.review_status!=s.ReviewStatus.APPROVED:raise ServiceError(409,'VOICE_REVIEW_REQUIRED','Speech requires an approved source notice')
        with self.ai.store.connect() as con:row=con.execute('SELECT payload FROM v2_updates WHERE notice_id=?',(notice_id,)).fetchone()
        if not row:raise ServiceError(404,'UPDATE_NOT_FOUND','No reviewed update exists')
        update=s.NoticeUpdate.model_validate_json(row[0])
        return self.synthesize(guard_facts(update.summary_hi or update.summary_en,update.evidence),'hi-IN' if update.summary_hi else 'en-IN')

    def synthesize(self,text,language):
        if len(text)>2500:raise ServiceError(422,'VOICE_TEXT_LIMIT','Reviewed text exceeds the speech limit')
        key='voice-output-'+hashlib.sha256((text+language+'bulbul:v4-flash:guard1').encode()).hexdigest()
        with self.ai.store.connect() as con:cached=con.execute('SELECT payload FROM v2_ai_cache WHERE cache_key=?',(key,)).fetchone()
        if cached:
            result=s.NoticeAudio.model_validate_json(cached[0])
            if result.text!=text:raise ServiceError(409,'VOICE_FACT_GUARD','Cached speech differs from current reviewed text')
            validate_audio({'audios':[result.audio_base64]});result.cache_hit=True;return result
        result=self.request(key,'text-to-speech',payload={'text':text,'language_code':language,'model':'bulbul:v4-flash','output_audio_codec':'wav','speech_sample_rate':22050},validate=validate_audio,cache=lambda data:s.NoticeAudio(text=text,audio_base64=data['audios'][0],cache_hit=False))
        try:
            encoded=result['audios'][0];raw=base64.b64decode(encoded,validate=True);wav_duration(raw)
        except (KeyError,IndexError,TypeError,ValueError):raise ServiceError(503,'VOICE_RESPONSE_INVALID','Provider did not return usable WAV audio') from None
        result=s.NoticeAudio(text=text,audio_base64=encoded,cache_hit=False)
        return result


def validate_transcript(result):
    if not isinstance(result.get('transcript'),str) or not 0<len(result['transcript'].strip())<=4000:raise ValueError('Invalid transcript')


def validate_audio(result):
    if len(result['audios'])!=1 or not isinstance(result['audios'][0],str) or len(result['audios'][0])>12*1024*1024:raise ValueError('Invalid audio')
    wav_duration(base64.b64decode(result['audios'][0],validate=True))
