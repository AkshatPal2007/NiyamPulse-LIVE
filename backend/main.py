"""Authenticated exam platform; one process with persistent SQLite storage."""
from contextlib import asynccontextmanager
from datetime import date, datetime
import logging
import os
from pathlib import Path
import sqlite3
import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import HttpUrl
from starlette.exceptions import HTTPException

from backend.legacy_schemas_v1 import (
    ApiError, ApplyAmendmentRequest, ApplyAmendmentResponse, DocumentExtraction,
    DocumentKind, EventFeedResponse, HealthResponse, ImportDocumentResponse,
    PreviewAmendmentResponse, ReviewOriginalRequest, TimelineSnapshot, WorkspaceState,
)
from backend.services.pdf_intake import MAX_PDF_BYTES
from backend.services.rule_engine import EngineError
from backend.services.watcher import LocalAmendmentWatcher
from backend.services.workspace import WorkspaceService
from backend.storage import ServiceError, Store, WorkspaceConfig


def create_app(store=None, *, clock=None, enable_watchers=True, v2_demo=None, enable_web_monitor=None,
               auth_settings=None, mailer=None, legacy_api_test=False):
    from backend.services.auth import AuthSettings
    account_settings=auth_settings or AuthSettings.from_env()
    @asynccontextmanager
    async def lifespan(app):
        from backend.operations import production_runtime
        with production_runtime(account_settings,enforce=store is None):
            app.state.store = store or Store(Path(os.environ.get("NIYAMPULSE_DATA_DIR", "var/production")) / "niyampulse.sqlite3")
            app.state.service = WorkspaceService(app.state.store, clock)
            app.state.watchers = {}
            from backend.exam_store import ExamStore
            from backend.services.exams import ExamService
            from backend.services.source_monitor import SourceMonitor, SourceScheduler
            from backend.services.sarvam import SarvamService
            from backend.services.vision import VisionService
            app.state.exam_store = store if isinstance(store, ExamStore) else ExamStore(app.state.store.path)
            # Only explicit test factories can opt into the retained fixture identity
            # mechanism. Environment settings never enable role impersonation.
            demo_enabled=bool(v2_demo) if v2_demo is not None else False
            if account_settings.production and demo_enabled:raise RuntimeError('Demo identities cannot be enabled in production')
            app.state.exam_service = ExamService(app.state.exam_store, demo=demo_enabled, clock=clock)
            from backend.services.auth import AuthService
            app.state.auth_service=AuthService(app.state.exam_store,settings=account_settings,mailer=mailer,clock=clock)
            app.state.source_monitor = SourceMonitor(app.state.exam_store, clock=clock)
            app.state.sarvam_service = SarvamService(app.state.exam_store, clock=clock)
            app.state.vision_service = VisionService(app.state.sarvam_service)
            web_monitor_enabled=enable_web_monitor if enable_web_monitor is not None else os.environ.get("NIYAMPULSE_WEB_MONITOR","1")=="1"
            from backend.services.processing import ProcessingService,ProcessingScheduler
            app.state.processing_service=ProcessingService(app.state.sarvam_service,app.state.vision_service,clock=clock)
            app.state.processing_scheduler=ProcessingScheduler(app.state.processing_service) if web_monitor_enabled else None
            if app.state.processing_scheduler:app.state.processing_scheduler.start()
            app.state.web_scheduler = SourceScheduler(app.state.source_monitor) if web_monitor_enabled else None
            if app.state.web_scheduler:
                app.state.web_scheduler.start()
            app.state.service.resume_pending()
            if enable_watchers:
                with app.state.store.connect() as con:
                    configs = [WorkspaceConfig.model_validate_json(row[0]) for row in con.execute("SELECT config FROM workspaces")]
                for config in configs:
                    if config.intake_directory:
                        watcher = LocalAmendmentWatcher(app.state.service, config.workspace_id, config.intake_directory)
                        watcher.start()
                        app.state.watchers[config.workspace_id] = watcher
            try:
                yield
            finally:
                if app.state.processing_scheduler:app.state.processing_scheduler.stop()
                if app.state.web_scheduler:
                    app.state.web_scheduler.stop()
                for watcher in app.state.watchers.values():
                    watcher.stop()

    app = FastAPI(title="NiyamPulse v2 · Exam intelligence", version="2.0.0", lifespan=lifespan,
                  docs_url=None if account_settings.production else '/docs',
                  redoc_url=None if account_settings.production else '/redoc',
                  openapi_url=None if account_settings.production else '/openapi.json')
    from backend.api.exams import router
    app.include_router(router)
    from backend.api.auth import router as auth_router
    app.include_router(auth_router)
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    frontend_dist=Path(__file__).resolve().parents[1]/"frontend"/"dist"
    if (frontend_dist/"assets").is_dir():
        app.mount("/assets",StaticFiles(directory=frontend_dist/"assets"),name="frontend-assets")

    @app.get("/",include_in_schema=False)
    def frontend():
        if not (frontend_dist/"index.html").is_file():
            raise ServiceError(503,"FRONTEND_NOT_BUILT","Build the frontend with npm --prefix frontend run build, then restart the backend")
        return FileResponse(frontend_dist/"index.html")

    @app.get('/favicon.svg',include_in_schema=False)
    def favicon():
        icon=frontend_dist/'favicon.svg'
        if not icon.is_file():raise ServiceError(404,'ICON_NOT_BUILT','Build frontend assets first')
        return FileResponse(icon,media_type='image/svg+xml')
    app.add_middleware(CORSMiddleware,allow_origins=list(account_settings.allowed_origins),allow_credentials=True,
                       allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Content-Type','X-CSRF-Token','Authorization'])
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from urllib.parse import urlsplit
    hosts=[urlsplit(account_settings.origin).hostname]
    if not account_settings.production:hosts+=['127.0.0.1','localhost','testserver']
    if account_settings.production and os.environ.get('RENDER')=='true':
        external=os.environ.get('RENDER_EXTERNAL_HOSTNAME','')
        import re
        if re.fullmatch(r'[a-z0-9-]+\.onrender\.com',external):hosts.append(external)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=hosts)
    from backend.security import AccountRequestLimit
    app.add_middleware(AccountRequestLimit)

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = uuid.uuid4().hex
        path=request.url.path
        try:
            auth=app.state.auth_service
            demo_request=app.state.exam_service.demo and (path=='/api/v2/demo/session' or request.headers.get('authorization','').startswith('Bearer '))
            legacy_test_request=legacy_api_test and path.startswith('/api/v1/')
            if path.startswith('/api/') and request.method in {'POST','PATCH','DELETE','PUT'} and not demo_request and not legacy_test_request:
                raw=request.cookies.get(auth.settings.cookie_name)
                anonymous_actions={'register','login','verify','reset-password','forgot-password','resend-verification'}
                if raw or path.startswith('/api/v2/auth/') or path=='/api/v2/demo/session':auth.check_origin(request.headers.get('origin'))
                if raw and path.rsplit('/',1)[-1] not in anonymous_actions:
                    if path!='/api/v2/auth/logout':auth.identity(raw)
                    auth.check_csrf(raw,request.headers.get('x-csrf-token'))
            if path.startswith('/api/v1/') and path!='/api/v1/health' and not legacy_test_request:
                user=auth.identity(request.cookies.get(auth.settings.cookie_name))
                if user['role']!='ADMIN':raise ServiceError(403,'ADMIN_REQUIRED','Legacy operations are restricted to administrators')
            response = await call_next(request)
        except ServiceError as error:response=failure(request,error.status,error.code,str(error))
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        connect="'self'" if account_settings.production else "'self' ws://localhost:5173 ws://127.0.0.1:5173"
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src "+connect+"; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        elif path=='/':response.headers['Cache-Control']='no-cache'
        elif path.startswith('/assets/'):response.headers['Cache-Control']='public, max-age=31536000, immutable'
        if account_settings.production:response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response

    def failure(request, status, code, message):
        if request.url.path.startswith("/api/v2"):
            from backend.schemas import ApiError as V2ApiError
            payload = V2ApiError(code=code,message=message,request_id=getattr(request.state,"request_id",uuid.uuid4().hex))
        else:
            payload = ApiError(error_code=code, message=message, request_id=getattr(request.state, "request_id", uuid.uuid4().hex))
        return JSONResponse(status_code=status, content=payload.model_dump(mode="json"), headers={"X-Request-ID":payload.request_id})

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        return failure(request, error.status, error.code, str(error))

    @app.exception_handler(EngineError)
    async def engine_error(request: Request, error: EngineError):
        return failure(request, 409, error.code, str(error))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return failure(request, 422, "VALIDATION_ERROR", "Request fields do not match the API contract")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return failure(request, error.status_code, "HTTP_ERROR", str(error.detail))

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, error: sqlite3.Error):
        return failure(request, 500, "DATABASE_ERROR", "Database operation failed; changes were rolled back")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logging.getLogger(__name__).exception("Request failed; request_id=%s", getattr(request.state, "request_id", "unknown"))
        return failure(request, 500, "INTERNAL_ERROR", "Request failed; no successful operation is claimed")

    def workspace_state(workspace_id):
        state = app.state.store.state(workspace_id)
        watcher = app.state.watchers.get(workspace_id)
        if watcher:
            state.watcher = watcher.health()
        return state

    from backend.schemas import ServiceHealth

    @app.get('/api/v2/health/live',response_model=ServiceHealth)
    def live():
        return ServiceHealth(status='OK',checks={'application':True},
                             monitoring_enabled=app.state.web_scheduler is not None)

    @app.get('/api/v2/health/ready',response_model=ServiceHealth,responses={503:{'model':ServiceHealth}})
    def ready(response:Response):
        from backend.operations import readiness_checks
        checks=readiness_checks(app)
        ok=all(checks.values())
        if not ok:response.status_code=503
        return ServiceHealth(status='OK' if ok else 'NOT_READY',checks=checks,
                             monitoring_enabled=app.state.web_scheduler is not None)

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health():
        return HealthResponse()

    @app.get("/api/v1/workspaces/{workspace_id}", response_model=WorkspaceState)
    def get_workspace(workspace_id: str):
        return workspace_state(workspace_id)

    @app.post("/api/v1/workspaces/{workspace_id}/documents", response_model=ImportDocumentResponse, status_code=202)
    async def import_document(workspace_id: str, background_tasks: BackgroundTasks,
                              file: UploadFile = File(...), kind: DocumentKind = Form(...),
                              source_url: HttpUrl | None = Form(None)):
        try:
            data = await file.read(MAX_PDF_BYTES + 1)
        finally:
            await file.close()
        result = app.state.service.import_pdf(workspace_id, data, filename=file.filename, kind=kind, source_url=source_url)
        background_tasks.add_task(app.state.service.process, workspace_id, result.document.document_id)
        return result

    @app.get("/api/v1/workspaces/{workspace_id}/documents/{document_id}/pdf", response_class=Response)
    def get_pdf(workspace_id: str, document_id: str):
        data = app.state.store.pdf(workspace_id, document_id)
        return Response(data, media_type="application/pdf", headers={"Content-Disposition":"inline", "X-Content-Type-Options":"nosniff"})

    @app.get("/api/v1/workspaces/{workspace_id}/documents/{document_id}/extraction", response_model=DocumentExtraction)
    def get_extraction(workspace_id: str, document_id: str):
        return app.state.store.extraction(workspace_id, document_id)

    @app.post("/api/v1/workspaces/{workspace_id}/documents/{document_id}/review", response_model=WorkspaceState)
    def review_original(workspace_id: str, document_id: str, body: ReviewOriginalRequest):
        app.state.service.review_original(workspace_id, document_id, body)
        return workspace_state(workspace_id)

    @app.get("/api/v1/workspaces/{workspace_id}/amendments/{amendment_id}/preview", response_model=PreviewAmendmentResponse)
    def preview(workspace_id: str, amendment_id: str):
        return app.state.service.preview(workspace_id, amendment_id)

    @app.post("/api/v1/workspaces/{workspace_id}/amendments/{amendment_id}/apply", response_model=ApplyAmendmentResponse)
    def apply(workspace_id: str, amendment_id: str, body: ApplyAmendmentRequest):
        return app.state.service.apply(workspace_id, amendment_id, body)

    @app.get("/api/v1/workspaces/{workspace_id}/timeline", response_model=TimelineSnapshot)
    def timeline(workspace_id: str, as_of_date: date, known_at: datetime | None = None):
        return app.state.service.timeline(workspace_id, as_of_date, known_at)

    @app.get("/api/v1/workspaces/{workspace_id}/events", response_model=EventFeedResponse)
    def events(workspace_id: str, cursor: str | None = None):
        return app.state.store.events(workspace_id, cursor)

    @app.get("/api/v1/workspaces/{workspace_id}/evaluations/latest", responses={404:{"model":ApiError}})
    def evaluation(workspace_id: str):
        app.state.store.config(workspace_id)
        raise ServiceError(404, "NO_EVALUATION_RUN", "No persisted evaluation run exists")

    return app


app = create_app()
