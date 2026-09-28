"""MedRAG-X FastAPI application."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.schemas import (
    DemoLoadRequest,
    DocumentInfo,
    ProcessResponse,
    QueryRequest,
    QueryResponse,
    HealthResponse,
)
from app.config import settings
from app.documents.loader import DocumentError
from app.embeddings.provider import get_embedder
from app.llm.provider import get_llm_provider
from app.rag.pipeline import RagPipeline
from app.rag.sessions import store as session_store
from app.utils.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MedRAG-X API",
    version=__version__,
    description=(
        "Evidence-grounded medical research assistant API (educational demo). "
        "Not a medical device. Does not provide diagnosis or treatment advice."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

pipeline = RagPipeline()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(DocumentError)
async def document_error_handler(_request: Request, exc: DocumentError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "INVALID_DOCUMENT", "message": str(exc)}},
    )


@app.exception_handler(RuntimeError)
async def session_error_handler(_request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=409,
        content={"error": {"code": "SESSION_NOT_READY", "message": str(exc)}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error. Check backend logs."}},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    embedder = get_embedder()
    llm = get_llm_provider()
    return HealthResponse(
        status="ok",
        version=__version__,
        embedding_model=embedder.name,
        embedding_backend=type(embedder).__name__,
        vector_backend="faiss",
        llm_provider=llm.name,
        llm_model=llm.model,
        llm_configured=bool(settings.llm_api_key),
    )


# ---------- Document endpoints ----------


@app.post("/api/sessions")
def create_session() -> dict:
    """Create an empty session so uploads can precede any demo load."""
    session = session_store.create()
    return {"session_id": session.session_id, "document": session.summary()}


@app.post("/api/documents/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
) -> ProcessResponse:
    session = session_store.get(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "SESSION_NOT_FOUND", "message": "Unknown session. Start the demo first."}},
        )
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File exceeds the {settings.max_upload_mb} MB limit.",
                }
            },
        )
    result = pipeline.ingest_document(session, file.filename or "upload", data)
    return ProcessResponse(
        session_id=session.session_id,
        document=DocumentInfo(
            document_name=result["document_name"],
            document_type=result["document_type"],
            status=session.status,
            chunk_count=result["chunk_count"],
            chunk_params=result["chunk_params"],
        ),
    )


@app.post("/api/documents/demo", response_model=ProcessResponse)
def load_demo(body: DemoLoadRequest | None = None) -> ProcessResponse:
    body = body or DemoLoadRequest()
    session = session_store.create()
    try:
        result = pipeline.ingest_demo(session, body.filename)
    except KeyError as exc:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "DEMO_NOT_FOUND", "message": str(exc)}},
        )
    return ProcessResponse(
        session_id=session.session_id,
        document=DocumentInfo(
            document_name=result["document_name"],
            document_type=result["document_type"],
            status=session.status,
            chunk_count=result["chunk_count"],
            chunk_params=result["chunk_params"],
        ),
    )


@app.post("/api/query", response_model=QueryResponse)
def query(body: QueryRequest) -> QueryResponse:
    session = session_store.get(body.session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "SESSION_NOT_FOUND", "message": "Unknown or expired session."}},
        )
    if session.status != "ready":
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "SESSION_NOT_READY",
                    "message": "Process a document before asking questions.",
                }
            },
        )
    result = pipeline.answer(session, body.question, top_k=body.top_k)
    return QueryResponse(**result)


@app.post("/api/session/reset")
def reset_session(body: QueryRequest) -> dict:
    session = session_store.get(body.session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "SESSION_NOT_FOUND", "message": "Unknown or expired session."}},
        )
    session_store.reset(session)
    return {"session_id": body.session_id, "status": "reset", "document": session.summary()}


# ---------- App lifecycle ----------


@app.on_event("startup")
def warmup() -> None:
    logger.info("MedRAG-X backend starting (v%s)", __version__)
    get_embedder()  # load embedding model once at boot, not on first query
    get_llm_provider()
    logger.info("Warmup complete: embeddings + LLM provider ready")
