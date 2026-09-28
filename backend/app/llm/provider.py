"""LLM providers.

`generate_answer(question, evidence)` is the single integration point (see
docs in RAG_DOCUMENTATION.md). Two implementations:

- GroqProvider: Groq Cloud OpenAI-compatible chat API (free tier, no credit
  card). Model configurable via LLM_MODEL (default openai/gpt-oss-120b).
- MockLLMProvider: deterministic extractive fallback used when no API key is
  configured or the API fails. It composes an answer from the retrieved
  evidence only — it never invents content. Responses are clearly labeled so
  it can never be mistaken for real LLM output.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import settings
from app.llm.prompts import build_user_message, build_evidence_block

logger = logging.getLogger(__name__)

INSUFFICIENT_PHRASES = (
    "does not contain sufficient",
    "do not contain sufficient",
    "not sufficient",
    "insufficient information",
    "not enough information",
    "do not contain enough",
    "cannot be answered from",
)


@dataclass
class GenerationResult:
    answer: str
    provider: str
    model: str
    used_fallback: bool = False
    latency_ms: int = 0
    prompt_chars: int = 0
    error: str | None = None
    raw_context: str = field(default="", repr=False)


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_answer(
        self, question: str, evidence: list[dict], history_block: str = ""
    ) -> GenerationResult: ...


def _is_insufficient(answer: str) -> bool:
    low = answer.lower()
    return any(p in low for p in INSUFFICIENT_PHRASES)


class GroqProvider:
    """Groq Cloud chat completions (OpenAI-compatible endpoint)."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.name = "groq"
        self.model = model

    def generate_answer(
        self, question: str, evidence: list[dict], history_block: str = ""
    ) -> GenerationResult:
        from app.llm.prompts import SYSTEM_PROMPT

        user_msg = build_user_message(question, evidence, history_block)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
            "max_completion_tokens": 700,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        last_error: str | None = None
        for attempt in range(settings.llm_max_retries + 1):
            start = time.perf_counter()
            try:
                with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                    resp = client.post(self.API_URL, json=payload, headers=headers)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after", "2")
                    last_error = f"Groq rate limit hit (429); retry-after {retry_after}s"
                    logger.warning(last_error)
                    time.sleep(min(float(retry_after), 5.0))
                    continue
                resp.raise_for_status()
                data = resp.json()
                answer = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                if not answer:
                    last_error = "Groq returned an empty completion"
                    continue
                return GenerationResult(
                    answer=answer,
                    provider=self.name,
                    model=self.model,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    prompt_chars=len(user_msg),
                    raw_context=user_msg,
                )
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_error = f"Groq request failed: {exc}"
                logger.warning(last_error)
                time.sleep(0.5 * (attempt + 1))

        return GenerationResult(
            answer="The answer service is temporarily unavailable (LLM provider error). Please retry shortly.",
            provider=self.name,
            model=self.model,
            used_fallback=True,
            latency_ms=0,
            prompt_chars=len(user_msg),
            error=last_error,
            raw_context=user_msg,
        )


class MockLLMProvider:
    """Deterministic extractive answerer (no network, no key).

    Selects the 1-3 most query-relevant sentences from the retrieved evidence
    and labels the output as extractive. Used when LLM_API_KEY is unset and as
    a graceful degradation path when the API fails.
    """

    def __init__(self) -> None:
        self.name = "mock-extractive"
        self.model = "extractive-sentence-selection"

    def generate_answer(
        self, question: str, evidence: list[dict], history_block: str = ""
    ) -> GenerationResult:
        start = time.perf_counter()
        if not evidence:
            answer = (
                "The provided documents do not contain sufficient information to answer "
                "this question — no relevant evidence was retrieved. Try rephrasing the "
                "question or processing a relevant document."
            )
            return GenerationResult(
                answer=answer, provider=self.name, model=self.model, latency_ms=1, raw_context=""
            )

        from app.retrieval.retriever import _lexical_similarity

        # Follow-up heuristic for the extractive fallback: questions containing
        # anaphora ("what evidence supports THAT?") are ranked against the
        # previous user question too, so the prior topic stays retrievable.
        effective_question = question
        if history_block and re.search(r"\b(that|this|it|those|these|they)\b", question.lower()):
            last_user = ""
            for line in history_block.splitlines():
                if line.startswith("User:"):
                    last_user = line[5:].strip()
            if last_user:
                effective_question = f"{question} {last_user}"

        sentences: list[tuple[float, float, int, str, dict]] = []
        for i, ev in enumerate(evidence, start=1):
            for sent in re.split(r"(?<=[.!?])\s+", ev["text"]):
                sent = sent.strip()
                if len(sent) < 40:
                    continue
                lex = _lexical_similarity(effective_question, sent)
                # Rank by lexical + small evidence bonus, but gate refusal on
                # PURE lexical similarity so the bonus can't mask irrelevance.
                rank = lex + 0.1 * ev.get("score", 0.0)
                sentences.append((rank, lex, i, sent, ev))

        sentences.sort(key=lambda t: t[0], reverse=True)
        picked: list[tuple[int, str]] = []
        best_lex = sentences[0][1] if sentences else 0.0
        for _rank, lex, src_idx, sent, _ev in sentences:
            if len(picked) >= 3:
                break
            # Weak best match means the documents likely do not answer the
            # question — refuse honestly instead of parroting weakly-related text.
            if lex <= 0.02 or lex < best_lex * 0.5:
                continue
            if any(sent == s for _, s in picked):
                continue
            picked.append((src_idx, sent))

        if not picked:
            # Weak lexical overlap — report insufficiency honestly.
            answer = (
                "The provided documents do not contain sufficient information to answer "
                "this question. No passage in the retrieved evidence closely matches it."
            )
        else:
            parts = [f"[{idx}] {sent}" for idx, sent in picked]
            answer = "Based on the provided documents (extractive fallback mode, no LLM key configured):\n\n" + "\n\n".join(parts)

        user_msg = build_user_message(question, evidence, history_block)
        return GenerationResult(
            answer=answer,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            prompt_chars=len(user_msg),
            raw_context=user_msg,
        )


_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Factory honoring configuration; one instance per process."""
    global _provider
    if _provider is not None:
        return _provider
    api_key = settings.llm_api_key or os.environ.get("GROQ_API_KEY", "")
    if api_key.strip():
        _provider = GroqProvider(api_key.strip(), settings.llm_model)
    else:
        logger.warning("LLM_API_KEY not set — using extractive MockLLMProvider")
        _provider = MockLLMProvider()
    return _provider


def reset_llm_provider() -> None:
    global _provider
    _provider = None
