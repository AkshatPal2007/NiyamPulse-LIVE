"""Real-account HTTP routes; email links are never returned through JSON."""
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from backend import schemas as s
from backend.api.exams import current_user

router = APIRouter(prefix='/api/v2/auth',tags=['Accounts'])


def service(request): return request.app.state.auth_service
def address(request): return request.client.host if request.client else 'unknown'


@router.get('/config',response_model=s.AuthConfig)
def config(request:Request): return service(request).config()


@router.post('/register',response_model=s.EmailActionResponse,status_code=202)
def register(body:s.RegisterRequest,request:Request,tasks:BackgroundTasks):
    tasks.add_task(service(request).dispatch,service(request).request_registration(body,address(request)))
    return s.EmailActionResponse()


@router.post('/forgot-password',response_model=s.EmailActionResponse,status_code=202)
def forgot_password(body:s.EmailRequest,request:Request,tasks:BackgroundTasks):
    tasks.add_task(service(request).dispatch,service(request).request_recovery(body.email,address(request)))
    return s.EmailActionResponse()


@router.post('/resend-verification',response_model=s.EmailActionResponse,status_code=202)
def resend(body:s.EmailRequest,request:Request,tasks:BackgroundTasks):
    tasks.add_task(service(request).dispatch,service(request).request_recovery(body.email,address(request),purpose='VERIFY'))
    return s.EmailActionResponse()


def finish(request,response,result):
    raw,session=result
    service(request).set_cookie(response,raw)
    return session


@router.post('/verify',response_model=s.AuthSession)
def verify(body:s.CompleteAccountRequest,request:Request,response:Response):
    service(request)._rate('verify',service(request)._digest(body.token.get_secret_value()),address(request),limit=12)
    return finish(request,response,service(request).complete(body.token.get_secret_value(),body.password.get_secret_value(),purpose='VERIFY'))


@router.post('/reset-password',response_model=s.AuthSession)
def reset(body:s.CompleteAccountRequest,request:Request,response:Response):
    service(request)._rate('reset',service(request)._digest(body.token.get_secret_value()),address(request),limit=12)
    return finish(request,response,service(request).complete(body.token.get_secret_value(),body.password.get_secret_value(),purpose='RESET'))


@router.post('/login',response_model=s.AuthSession)
def login(body:s.LoginRequest,request:Request,response:Response):
    return finish(request,response,service(request).login(body.email,body.password.get_secret_value(),address(request)))


@router.get('/session',response_model=s.AuthSession)
def session(request:Request):
    return service(request).session(request.cookies.get(service(request).settings.cookie_name))


@router.post('/logout',status_code=204)
def logout(request:Request,response:Response):
    service(request).logout(response,request.cookies.get(service(request).settings.cookie_name))
    response.status_code=204


@router.post('/password',status_code=204)
def change_password(body:s.PasswordChangeRequest,request:Request,response:Response,user=Depends(current_user)):
    service(request)._rate('change-password',user['email'],address(request),limit=5)
    service(request).change_password(user['id'],body.current_password.get_secret_value(),body.new_password.get_secret_value())
    service(request).logout(response,request.cookies.get(service(request).settings.cookie_name))
    response.status_code=204
