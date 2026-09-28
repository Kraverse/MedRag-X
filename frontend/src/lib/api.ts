export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parseError(resp: Response): Promise<ApiError> {
  try {
    const body = (await resp.json()) as { error?: { code?: string; message?: string } };
    return new ApiError(resp.status, body.error?.code ?? "UNKNOWN", body.error?.message ?? resp.statusText);
  } catch {
    return new ApiError(resp.status, "UNKNOWN", `Request failed (${resp.status})`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "BACKEND_UNAVAILABLE", "Cannot reach the MedRAG-X backend. It may be waking up — retry in a few seconds.");
  }
  if (!resp.ok) throw await parseError(resp);
  return (await resp.json()) as T;
}

// ---------- types ----------

export interface DocumentInfo {
  document_name: string | null;
  document_type: string | null;
  status: "empty" | "processing" | "ready" | "error";
  chunk_count: number;
  error?: string | null;
  chunk_params?: { chunk_size: number; chunk_overlap: number } | null;
}

export interface ProcessResponse {
  session_id: string;
  document: DocumentInfo;
}

export interface SourceCard {
  chunk_id: string;
  document_name: string;
  page: number | null;
  section: string | null;
  text: string;
  score: number;
  dense_score: number;
  lexical_score: number;
  citation: string;
}

export interface DebugInfo {
  embedding_model: string;
  embedding_backend: string;
  vector_backend: string;
  top_k: number;
  retrieved_count: number;
  scores: { chunk_id: string; final: number; dense: number; lexical: number }[];
  context_sent_to_llm: string;
  prompt_chars: number;
  conversation_history: { role: string; content: string }[];
}

export interface QueryResponse {
  session_id: string;
  question: string;
  answer: string;
  sources: SourceCard[];
  insufficient_evidence: boolean;
  provider: string;
  model: string;
  used_fallback: boolean;
  latency_ms: number;
  debug: DebugInfo;
}

export interface HealthResponse {
  status: string;
  version: string;
  embedding_model: string;
  embedding_backend: string;
  vector_backend: string;
  llm_provider: string;
  llm_model: string;
  llm_configured: boolean;
}

// ---------- endpoints ----------

export function createSession(): Promise<{ session_id: string; document: DocumentInfo }> {
  return request<{ session_id: string; document: DocumentInfo }>("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function loadDemoDocument(filename?: string): Promise<ProcessResponse> {
  return request<ProcessResponse>("/api/documents/demo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: filename ?? null }),
  });
}

export function uploadDocument(sessionId: string, file: File): Promise<ProcessResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("session_id", sessionId);
  return request<ProcessResponse>("/api/documents/process", { method: "POST", body: form });
}

export function sendQuery(sessionId: string, question: string): Promise<QueryResponse> {
  return request<QueryResponse>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
}

export function resetSession(sessionId: string): Promise<{ status: string }> {
  return request<{ status: string }>("/api/session/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, question: "reset" }),
  });
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

// ---------- demo catalog (names must match backend demo_documents.py) ----------

export interface DemoDoc {
  filename: string;
  title: string;
  description: string;
  tag: string;
}

export const DEMO_DOCS: DemoDoc[] = [
  {
    filename: "Sleep-Quality-and-Cognition.md",
    title: "Sleep Quality & Cognition",
    description: "Simulated review of sleep duration, regularity, attention, and decision-making.",
    tag: "Synthetic research review",
  },
  {
    filename: "Wearable-Heart-Rate-Accuracy.md",
    title: "Wearable Heart-Rate Accuracy",
    description: "Simulated evaluation of wrist-worn optical heart-rate monitors during exercise.",
    tag: "Synthetic technical report",
  },
  {
    filename: "Reading-Medical-Research-Primer.md",
    title: "Reading Medical Research",
    description: "Primer on study designs, bias, and evidence vocabulary.",
    tag: "Educational primer",
  },
];

export const HEALTH_DISCLAIMER =
  "MedRAG-X is an educational research assistant for exploring provided documents. It does not provide medical diagnosis or medical advice. Do not upload real patient records or sensitive personal information.";
