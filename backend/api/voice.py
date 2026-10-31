from fastapi import APIRouter,Depends,File,Request,UploadFile
from backend import schemas as s
from backend.api.exams import current_user
from backend.services.voice import VoiceService
from backend.storage import ServiceError

router=APIRouter(prefix='/api/v2/me',tags=['accessible audio'])

def service(request,user):
    auth=request.app.state.auth_service
    auth._rate('voice',user.get('email',user['id']),request.client.host if request.client else 'unknown',limit=5,window=60)
    return VoiceService(request.app.state.sarvam_service,request.app.state.exam_service)

@router.post('/voice-search',response_model=s.VoiceSearchResult)
async def voice_search(request:Request,file:UploadFile=File(...),user=Depends(current_user)):
    try:raw=await file.read(1024*1024+1)
    finally:await file.close()
    return service(request,user).transcribe(raw)

@router.post('/notifications/{notification_id}/audio',response_model=s.NoticeAudio)
def audio(notification_id:str,request:Request,user=Depends(current_user)):
    return service(request,user).speak(user['id'],notification_id)
