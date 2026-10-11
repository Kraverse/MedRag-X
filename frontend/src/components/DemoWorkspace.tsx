"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  DEMO_DOCS,
  HEALTH_DISCLAIMER,
  createSession,
  loadDemoDocument,
  resetSession,
  sendQuery,
  uploadDocument,
  DocumentInfo,
  QueryResponse,
  SourceCard,
} from "@/lib/api";

type Stage = "pick" | "processing" | "ready" | "error";

interface Turn {
  question: string;
  result: QueryResponse;
}

const SUGGESTED_QUESTIONS: Record<string, string[]> = {
  "Sleep-Quality-and-Cognition.md": [
    "What happens to attention after short sleep?",
    "Did sleep regularity matter, or only duration?",
    "What were the cohort sizes?",
  ],
  "Wearable-Heart-Rate-Accuracy.md": [
    "When are wrist heart-rate monitors least accurate?",
    "How did the devices compare during intervals?",
    "What error sources are discussed?",
  ],
  "Reading-Medical-Research-Primer.md": [
    "Which study designs sit at the top of the evidence pyramid?",
    "What is publication bias?",
    "What does number needed to treat mean?",
  ],
};

export default function DemoWorkspace() {
  const [stage, setStage] = useState<Stage>("pick");
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);
  const [showDebug, setShowDebug] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const answersEndRef = useRef<HTMLDivElement>(null);

  // Rehydrate an in-flight session after page refresh (best-effort; backend
  // sessions are in-memory and may be gone).
  useEffect(() => {
    const saved = window.sessionStorage.getItem("medrag_session");
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as { sessionId: string; document: DocumentInfo };
        setSessionId(parsed.sessionId);
        setDoc(parsed.document);
        setStage("ready");
      } catch {
        window.sessionStorage.removeItem("medrag_session");
      }
    }
  }, []);

  useEffect(() => {
    if (sessionId && doc) {
      window.sessionStorage.setItem("medrag_session", JSON.stringify({ sessionId, document: doc }));
    }
  }, [sessionId, doc]);

  useEffect(() => {
    answersEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns.length, asking]);

  const handleApiError = useCallback((err: unknown) => {
    if (err instanceof ApiError) {
      setError(
        err.code === "BACKEND_UNAVAILABLE"
          ? `${err.message} (If this is the first visit, the free-tier backend may need ~50 seconds to wake up.)`
          : err.message
      );
    } else {
      setError("Something went wrong. Please try again.");
    }
    setStage("error");
  }, []);

  async function chooseDemo(filename: string) {
    setError(null);
    setStage("processing");
    setStatusMsg("Loading and processing the demo document (chunking + embedding)…");
    try {
      const resp = await loadDemoDocument(filename);
      applyProcessed(resp.session_id, resp.document);
    } catch (err) {
      handleApiError(err);
    }
  }

  async function handleUpload(file: File) {
    setError(null);
    setStage("processing");
    setStatusMsg("Uploading and processing your document…");
    try {
      let sid = sessionId;
      if (!sid) {
        const created = await createSession();
        sid = created.session_id;
        setSessionId(sid);
      }
      const resp = await uploadDocument(sid, file);
      applyProcessed(sid, resp.document);
    } catch (err) {
      handleApiError(err);
    }
  }

  function applyProcessed(sid: string, document: DocumentInfo) {
    setSessionId(sid);
    setDoc(document);
    setTurns([]);
    setStage("ready");
    setStatusMsg(null);
  }

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed || !sessionId || asking) return;
    setError(null);
    setAsking(true);
    setQuestion("");
    try {
      const result = await sendQuery(sessionId, trimmed);
      setTurns((prev) => [...prev, { question: trimmed, result }]);
    } catch (err) {
      handleApiError(err);
    } finally {
      setAsking(false);
    }
  }

  async function handleReset() {
    if (sessionId) {
      try {
        await resetSession(sessionId);
      } catch {
        /* reset is best-effort client-side too */
      }
    }
    window.sessionStorage.removeItem("medrag_session");
    setSessionId(null);
    setDoc(null);
    setTurns([]);
    setQuestion("");
    setError(null);
    setStage("pick");
  }

  const lastTurn = turns.length > 0 ? turns[turns.length - 1] : null;
  const suggestions = doc ? SUGGESTED_QUESTIONS[doc.document_name ?? ""] ?? [] : [];

  return (
    <div className="space-y-6">
      {/* Document panel */}
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold text-slate-900">1 · Choose a document</h2>
            <p className="mt-1 text-sm text-slate-500">
              Pick a preloaded synthetic research document, or upload your own PDF/TXT/Markdown (max 10 MB).
            </p>
          </div>
          {stage === "ready" && (
            <button onClick={handleReset} className="btn-secondary !py-1.5 !px-3 text-xs">
              Reset session
            </button>
          )}
        </div>

        {stage === "pick" && (
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {DEMO_DOCS.map((d) => (
              <button
                key={d.filename}
                onClick={() => chooseDemo(d.filename)}
                className="card group p-4 text-left transition hover:border-teal-400 hover:shadow-sm"
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-teal-700">{d.tag}</span>
                <p className="mt-1 font-semibold text-slate-900 group-hover:text-teal-700">{d.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">{d.description}</p>
              </button>
            ))}
            <div className="md:col-span-3 rounded-xl border border-dashed border-teal-300 bg-teal-50/60 p-5 text-center">
              <p className="font-semibold text-slate-900">Have your own document?</p>
              <p className="mt-1 text-sm text-slate-600">
                Upload a PDF, TXT, or Markdown file and ask questions about its contents.
              </p>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="btn-primary mt-3 text-sm"
              >
                Upload a document
              </button>
              <p className="mt-2 text-xs text-slate-500">Maximum file size: 10 MB · Temporary session storage</p>
            </div>
          </div>
        )}

        {stage === "processing" && (
          <div className="mt-4 flex items-center gap-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
            {statusMsg}
          </div>
        )}

        {stage === "ready" && doc && (
          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg bg-teal-50 p-4 text-sm">
            <span className="font-semibold text-teal-900">{doc.document_name}</span>
            <span className="text-teal-700">{doc.document_type}</span>
            <span className="rounded-full bg-teal-600 px-2 py-0.5 text-xs font-semibold text-white">ready</span>
            <span className="text-teal-800">
              {doc.chunk_count} chunks · {doc.chunk_params?.chunk_size ?? 1200} chars · overlap{" "}
              {doc.chunk_params?.chunk_overlap ?? 200}
            </span>
          </div>
        )}

        {stage === "ready" && (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-xs font-medium text-teal-700 underline hover:text-teal-800"
            >
              Upload a different document (PDF / TXT / Markdown, max 10 MB)
            </button>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleUpload(f);
            e.target.value = "";
          }}
        />

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
            <button onClick={handleReset} className="ml-2 font-semibold underline">
              Start over
            </button>
          </div>
        )}
      </section>

      {/* Q&A panel */}
      {stage === "ready" && (
        <section className="card p-5">
          <h2 className="font-semibold text-slate-900">2 · Ask questions</h2>

          {suggestions.length > 0 && turns.length === 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => void ask(s)}
                  className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 transition hover:border-teal-400 hover:text-teal-700"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <form
            className="mt-4 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void ask(question);
            }}
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask anything about the document…"
              className="flex-1 rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
              disabled={asking}
              maxLength={1000}
            />
            <button type="submit" disabled={asking || !question.trim()} className="btn-primary text-sm">
              {asking ? "Retrieving…" : "Ask"}
            </button>
          </form>

          {asking && (
            <div className="mt-5 flex items-center gap-3 text-sm text-slate-500">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
              Embedding the question and searching {doc?.chunk_count} chunks…
            </div>
          )}

          <div className="mt-6 space-y-6">
            {turns.map((turn, i) => (
              <AnswerBlock key={i} turn={turn} showDebug={showDebug} />
            ))}
            <div ref={answersEndRef} />
          </div>

          {turns.length > 0 && (
            <label className="mt-6 flex items-center gap-2 text-xs text-slate-500">
              <input type="checkbox" checked={showDebug} onChange={(e) => setShowDebug(e.target.checked)} />
              Show Technical Details for all answers
            </label>
          )}
        </section>
      )}

      <p className="px-1 text-xs leading-relaxed text-slate-400">{HEALTH_DISCLAIMER}</p>
    </div>
  );
}

function AnswerBlock({ turn, showDebug }: { turn: Turn; showDebug: boolean }) {
  const { result } = turn;
  return (
    <article className="rounded-xl border border-slate-200 p-5">
      <p className="text-sm font-semibold text-slate-800">
        <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs font-bold text-slate-500">Q</span>
        {turn.question}
      </p>

      <div className="mt-4 rounded-lg border-l-4 border-teal-600 bg-white p-4">
        <AnswerText answer={result.answer} sources={result.sources} />
        <p className="mt-3 text-xs text-slate-400">
          {result.provider}/{result.model} · {result.latency_ms} ms · {result.sources.length} sources
          {result.insufficient_evidence && " · insufficient evidence flagged"}
        </p>
      </div>

      {/* Sources */}
      {result.sources.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</p>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {result.sources.map((s, i) => (
              <SourceChip key={s.chunk_id} source={s} index={i + 1} />
            ))}
          </div>
        </div>
      )}

      <TechnicalDetails result={result} defaultOpen={showDebug} />
    </article>
  );
}

function AnswerText({ answer, sources }: { answer: string; sources: SourceCard[] }) {
  // Render [n] citation markers as chips linked to source numbering.
  const parts = answer.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
      {parts.map((part, i) => {
        const m = part.match(/\[(\d+)\]/);
        if (!m) return <span key={i}>{part}</span>;
        const n = parseInt(m[1], 10);
        const src = sources[n - 1];
        return (
          <span key={i} className="citation-chip" title={src ? src.citation : `Source ${n}`}>
            [{n}]
          </span>
        );
      })}
    </p>
  );
}

function SourceChip({ source, index }: { source: SourceCard; index: number }) {
  return (
    <details className="card group p-3">
      <summary className="flex items-start justify-between gap-2 text-xs">
        <span className="font-semibold text-slate-700">
          <span className="mr-1.5 inline-flex h-4 w-4 items-center justify-center rounded bg-teal-100 text-[10px] font-bold text-teal-700">
            {index}
          </span>
          {source.document_name}
          <span className="ml-1 font-normal text-slate-400">
            {source.page != null
              ? `· Page ${source.page}`
              : `· Chunk ${source.chunk_id.match(/c(\d+)$/)?.[1] ?? source.chunk_id}`}
          </span>
        </span>
        <span className="chevron text-slate-400">▶</span>
      </summary>
      {source.section && <p className="mt-1 text-[11px] text-teal-700">§ {source.section}</p>}
      <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">{source.text}</p>
      <p className="mt-2 text-[10px] text-slate-400">
        score {source.score.toFixed(3)} (dense {source.dense_score.toFixed(3)} + lexical{" "}
        {source.lexical_score.toFixed(3)})
      </p>
    </details>
  );
}

function TechnicalDetails({ result, defaultOpen }: { result: QueryResponse; defaultOpen: boolean }) {
  return (
    <details className="mt-4 rounded-lg border border-slate-200 bg-slate-50" open={defaultOpen}>
      <summary className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-slate-600">
        <span className="chevron">▶</span> Technical Details
      </summary>
      <div className="space-y-3 border-t border-slate-200 px-4 py-3 text-xs text-slate-600">
        <div>
          <p className="font-semibold text-slate-700">Pipeline</p>
          <p>
            embedder {result.debug.embedding_model} ({result.debug.embedding_backend}) · vector index{" "}
            {result.debug.vector_backend} · top_k {result.debug.top_k} · retrieved {result.debug.retrieved_count}
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-700">Similarity scores</p>
          <table className="mt-1 w-full max-w-md">
            <thead>
              <tr className="text-left text-[10px] uppercase text-slate-400">
                <th className="py-0.5">chunk</th>
                <th>final</th>
                <th>dense</th>
                <th>lexical</th>
              </tr>
            </thead>
            <tbody>
              {result.debug.scores.map((s) => (
                <tr key={s.chunk_id} className="border-t border-slate-200">
                  <td className="py-0.5 font-mono text-[10px]">{s.chunk_id}</td>
                  <td>{s.final.toFixed(3)}</td>
                  <td>{s.dense.toFixed(3)}</td>
                  <td>{s.lexical.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <p className="font-semibold text-slate-700">Context sent to the LLM ({result.debug.prompt_chars} chars)</p>
          <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded bg-white p-2 font-mono text-[10px] leading-relaxed text-slate-500">
            {result.debug.context_sent_to_llm}
          </pre>
        </div>
      </div>
    </details>
  );
}
