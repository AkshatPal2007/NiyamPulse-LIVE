from fastapi import APIRouter,Depends,Header,Query,Request,Response

from backend import schemas as s
from backend.storage import ServiceError

router=APIRouter(prefix="/api/v2",tags=["Exam notifications v2"])


def service(request:Request): return request.app.state.exam_service


def current_user(request:Request,authorization:str|None=Header(None)):
    return service(request).identity(authorization)


def admin(user=Depends(current_user)):
    if user["role"]!="ADMIN": raise ServiceError(403,"ADMIN_REQUIRED","Platform operator role is required")
    return user


@router.get("/status",response_model=s.PlatformStatus)
def status(request:Request):
    return s.PlatformStatus(demo_mode=service(request).demo,sarvam_status=request.app.state.sarvam_service.health().status)


@router.get("/admin/sarvam",response_model=s.SarvamHealth)
def sarvam_health(request:Request,user=Depends(admin)):
    return request.app.state.sarvam_service.health()


@router.post("/admin/notices/{notice_id}/analyze",response_model=s.NoticeAnalysis)
def analyze_notice(notice_id:str,body:s.AnalysisRequest,request:Request,user=Depends(admin)):
    return request.app.state.sarvam_service.process(notice_id,body.expected_revision)


@router.post("/admin/notices/{notice_id}/ocr",response_model=s.OcrResult)
def ocr_notice(notice_id:str,body:s.AnalysisRequest,request:Request,user=Depends(admin)):
    return request.app.state.vision_service.process(notice_id,body.expected_revision)


@router.post("/demo/session",response_model=s.SessionResponse)
def demo_session(body:s.DemoSessionRequest,request:Request):
    if request.client and request.client.host not in {"127.0.0.1","::1","testclient"}:
        raise ServiceError(403,"LOCAL_DEMO_ONLY","Demo role selection is available only on loopback")
    return service(request).login_demo(body.persona)


@router.get("/catalog",response_model=s.CatalogResponse)
def catalog(request:Request,audience:s.Audience|None=None,search:str|None=Query(None,max_length=120)):
    return service(request).store.catalog(audience,search)


@router.get("/me/subscriptions",response_model=list[s.ExamSubscription])
def subscriptions(request:Request,user=Depends(current_user)):
    return service(request).subscriptions(user["id"])


@router.post("/me/subscriptions",response_model=s.ExamSubscription)
def subscribe(body:s.SubscriptionCreate,request:Request,user=Depends(current_user)):
    return service(request).subscribe(user["id"],body)


@router.patch("/me/subscriptions/{subscription_id}",response_model=s.ExamSubscription)
def patch_subscription(subscription_id:str,body:s.SubscriptionPatch,request:Request,user=Depends(current_user)):
    return service(request).change_subscription(user["id"],subscription_id,body)


@router.delete("/me/subscriptions/{subscription_id}",status_code=204)
def unsubscribe(subscription_id:str,request:Request,user=Depends(current_user)):
    service(request).change_subscription(user["id"],subscription_id)
    return Response(status_code=204)


@router.get("/me/profile",response_model=s.UserProfileV2)
def profile(request:Request,user=Depends(current_user)):
    return service(request).profile(user["id"])


@router.patch("/me/profile",response_model=s.UserProfileV2)
def patch_profile(body:s.ProfilePatch,request:Request,user=Depends(current_user)):
    return service(request).profile(user["id"],body)


@router.delete("/me/profile/personalization",status_code=204)
def delete_personalization(request:Request,user=Depends(current_user)):
    service(request).profile(user["id"],clear=True)
    return Response(status_code=204)


@router.delete("/me/account",status_code=204)
def delete_account(request:Request,user=Depends(current_user)):
    if user["role"]!="USER": raise ServiceError(403,"USER_ACCOUNT_REQUIRED","Only learner accounts use this deletion endpoint")
    service(request).delete_account(user["id"])
    return Response(status_code=204)


@router.get("/me/notifications",response_model=s.NotificationsResponse)
def inbox(request:Request,cursor:str|None=Query(None,max_length=1000),limit:int=Query(30,ge=1,le=100),unread_only:bool=False,user=Depends(current_user)):
    return service(request).notifications(user["id"],cursor,limit,unread_only)


@router.get("/me/notifications/{notification_id}",response_model=s.InboxItem)
def notification(notification_id:str,request:Request,user=Depends(current_user)):
    return service(request).notification(user["id"],notification_id)


@router.post("/me/notifications/{notification_id}/read",response_model=s.InAppNotification)
def mark_read(notification_id:str,request:Request,user=Depends(current_user)):
    return service(request).notification(user["id"],notification_id,mark_read=True)


@router.get("/admin/dashboard",response_model=s.AdminDashboardResponse)
def dashboard(request:Request,user=Depends(admin)):
    return service(request).dashboard()


@router.get("/admin/sources",response_model=list[s.OfficialSource])
def sources(request:Request,user=Depends(admin)):
    return service(request).store.sources()


@router.get("/admin/notices",response_model=list[s.DetectedNotice])
def notices(request:Request,review_status:s.ReviewStatus|None=None,cycle_id:str|None=None,user=Depends(admin)):
    return service(request).notices(review_status,cycle_id)


@router.get("/admin/notices/{notice_id}",response_model=s.NoticeDetail)
def notice_detail(notice_id:str,request:Request,user=Depends(admin)):
    return service(request).notice_detail(notice_id)


@router.post("/admin/notices/{notice_id}/review",response_model=s.DetectedNotice)
def review(notice_id:str,body:s.NoticeReviewDecision,request:Request,user=Depends(admin)):
    return service(request).review(notice_id,body,user["id"])


@router.post("/admin/monitor/{source_id}/check",response_model=s.MonitorCheckResult)
def check(source_id:str,body:s.MonitorCheckRequest,request:Request,user=Depends(admin)):
    result=request.app.state.source_monitor.check(source_id,dry_run=body.dry_run)
    if result.errors: raise ServiceError(503,"SOURCE_UNAVAILABLE","; ".join(result.errors))
    return result


@router.post("/admin/demo/replay",response_model=list[s.DetectedNotice])
def replay(request:Request,user=Depends(admin)):
    if not service(request).demo: raise ServiceError(403,"DEMO_DISABLED","Synthetic replay is disabled")
    return request.app.state.source_monitor.replay_demo()


@router.get("/admin/updates/{update_id}/recipients",response_model=list[s.RecipientMatch])
def recipients(update_id:str,request:Request,user=Depends(admin)):
    return service(request).recipients(update_id)
