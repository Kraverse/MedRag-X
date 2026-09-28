"""Generation prompts.

One strict, provider-agnostic system prompt implements the anti-hallucination
contract required by the product: answer only from supplied evidence, no
invented citations, admit insufficient evidence, no diagnosis/treatment advice.
"""

SYSTEM_PROMPT = """You are MedRAG-X, an evidence-grounded research assistant for exploring documents the user has provided.

Strict rules:
1. Answer ONLY using the numbered EVIDENCE passages supplied in this message.
2. If the evidence does not contain enough information to answer, reply exactly that the provided documents do not contain sufficient information, and say what is missing.
3. Never invent facts, studies, numbers, or citations. Never cite a source that is not in the evidence.
4. Cite sources inline using the bracketed labels provided, e.g. [1] or [1][3].
5. Do not provide medical diagnosis, treatment, or medication advice. If asked, explain that MedRAG-X is an educational research tool and only reports what the documents say.
6. Be concise: 2-5 short paragraphs maximum, plain language, no markdown headings.
7. If the evidence is only weakly related to the question, prefer the insufficiency response over a speculative answer.
"""

USER_TEMPLATE = """QUESTION:
{question}
{history_section}
EVIDENCE:
{evidence_block}

Answer the question using only the numbered evidence above. Cite with [n] labels."""


def build_evidence_block(evidence_dicts: list[dict]) -> str:
    """Render retrieved chunks as a numbered block with citation metadata."""
    lines: list[str] = []
    for i, ev in enumerate(evidence_dicts, start=1):
        location = f"page {ev['page']}" if ev.get("page") is not None else f"chunk {ev['chunk_id']}"
        section = f", section '{ev['section']}'" if ev.get("section") else ""
        lines.append(
            f"[{i}] Source: {ev['document_name']} ({location}{section})\n{ev['text']}"
        )
    return "\n\n".join(lines)


def build_user_message(
    question: str, evidence_dicts: list[dict], history_block: str = ""
) -> str:
    """Compose the user message; history_block carries recent turns so
    follow-up questions ("what evidence supports that?") resolve correctly."""
    history_section = (
        f"CONVERSATION SO FAR (for resolving references like 'that'):\n{history_block}\n"
        if history_block.strip()
        else ""
    )
    return USER_TEMPLATE.format(
        question=question.strip(),
        history_section=history_section,
        evidence_block=build_evidence_block(evidence_dicts) or "(no evidence retrieved)",
    )
