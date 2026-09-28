import Link from "next/link";

const stages = [
  {
    title: "1 · Document processing",
    body: "Uploads (PDF, TXT, Markdown up to 10 MB) are validated, text is extracted (pypdf for PDFs, with page numbers preserved), cleaned of PDF artifacts, and split into overlapping 1,200-character chunks that keep section headings and page numbers as metadata.",
  },
  {
    title: "2 · Embedding",
    body: "Each chunk is embedded with BAAI/bge-small-en-v1.5 — a 33M-parameter open-source model (384 dimensions) that runs on CPU via ONNX. No GPU, no API key, no per-token cost.",
  },
  {
    title: "3 · Vector search",
    body: "Chunk vectors are indexed in a FAISS flat inner-product index. Your question is embedded with the same model, and cosine similarity retrieves the top-K most relevant chunks (K configurable, default 4). A small lexical-overlap bonus sharpens exact-phrase matches.",
  },
  {
    title: "4 · Grounded generation",
    body: "Retrieved chunks and the question go to an LLM (Groq-hosted openai/gpt-oss-120b on the free tier) behind a strict prompt: answer only from the numbered evidence, never invent citations, and say when the documents don't contain the answer.",
  },
  {
    title: "5 · Sources & transparency",
    body: "The response carries the exact retrieved passages with document name, page or chunk number, and similarity scores — plus a Technical Details view showing scores and the raw context sent to the model.",
  },
];

export default function HowItWorks() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-14">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">How MedRAG-X works</h1>
      <p className="mt-3 max-w-2xl text-slate-600">
        MedRAG-X is a complete Retrieval-Augmented Generation pipeline. Here is exactly what happens between your
        question and the cited answer.
      </p>

      <ol className="mt-10 space-y-4">
        {stages.map((s) => (
          <li key={s.title} className="card p-6">
            <h2 className="font-semibold text-teal-700">{s.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.body}</p>
          </li>
        ))}
      </ol>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/demo" className="btn-primary">
          Try it now →
        </Link>
        <Link href="/" className="btn-secondary">
          Back to home
        </Link>
      </div>

      <p className="mt-10 text-xs leading-relaxed text-slate-500">
        Full engineering details — chunking rationale, embedding model selection, evaluation metrics, and deployment
        architecture — live in the repository: RAG_DOCUMENTATION.md and RAG_EVALUATION.md.
      </p>
    </div>
  );
}
