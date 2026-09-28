"""Pydantic schemas: request validation and typed responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    version: str
    embedding_model: str
    embedding_backend: str
    vector_backend: str
    llm_provider: str
    llm_model: str
    llm_configured: bool


class DemoLoadRequest(BaseModel):
    filename: str | None = Field(
        default=None, description="Optional demo document filename; defaults to the first demo doc."
    )


class DocumentInfo(BaseModel):
    document_name: str | None
    document_type: str | None
    status: Literal["empty", "processing", "ready", "error"]
    chunk_count: int
    error: str | None = None
    chunk_params: dict[str, int] | None = None


class ProcessResponse(BaseModel):
    session_id: str
    document: DocumentInfo


class SourceCard(BaseModel):
    chunk_id: str
    document_name: str
    page: int | None
    section: str | None
    text: str
    score: float
    dense_score: float
    lexical_score: float
    citation: str


class QueryRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    question: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question must not be empty or whitespace.")
        return v.strip()


class DebugInfo(BaseModel):
    embedding_model: str
    embedding_backend: str
    vector_backend: str
    top_k: int
    retrieved_count: int
    scores: list[dict[str, Any]]
    context_sent_to_llm: str
    prompt_chars: int
    conversation_history: list[dict[str, str]]


class QueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    sources: list[SourceCard]
    insufficient_evidence: bool
    provider: str
    model: str
    used_fallback: bool
    latency_ms: int
    debug: DebugInfo


class ErrorResponse(BaseModel):
    error: dict[str, Any]
