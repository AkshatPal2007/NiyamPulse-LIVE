"""Local FastAPI service. Run uvicorn on 127.0.0.1; no remote auth is implemented."""
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

from backend.schemas import (
    ApiError, ApplyAmendmentRequest, ApplyAmendmentResponse, DocumentExtraction,
    DocumentKind, EventFeedResponse, HealthResponse, ImportDocumentResponse,
    PreviewAmendmentResponse, ReviewOriginalRequest, TimelineSnapshot, WorkspaceState,
)
from backend.services.pdf_intake import MAX_PDF_BYTES
from backend.services.rule_engine import EngineError
from backend.services.watcher import LocalAmendmentWatcher
from backend.services.workspace import WorkspaceService
from backend.storage import ServiceError, Store, WorkspaceConfig


def create_app(store=None, *, clock=None, enable_watchers=True):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = store or Store(Path(os.environ.get("NIYAMPULSE_DATA_DIR", "var")) / "niyampulse.sqlite3")
        app.state.service = WorkspaceService(app.state.store, clock)
        app.state.watchers = {}
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
            for watcher in app.state.watchers.values():
                watcher.stop()

    app = FastAPI(title="NiyamPulse LIVE", version="1.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def failure(request, status, code, message):
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
