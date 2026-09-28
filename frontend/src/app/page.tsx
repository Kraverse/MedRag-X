import Link from "next/link";
import { HEALTH_DISCLAIMER } from "@/lib/api";

const pipelineSteps = [
  { label: "Documents", desc: "PDF, TXT, or Markdown you provide" },
  { label: "Semantic Search", desc: "Embedded chunks matched to your question" },
  { label: "Relevant Evidence", desc: "Top passages ranked by similarity" },
  { label: "Grounded Answer", desc: "LLM answers only from that evidence" },
  { label: "Sources", desc: "Every claim traceable to its passage" },
];

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-6xl px-4 pt-16 pb-12 md:pt-24">
        <div className="max-w-3xl">
          <span className="mb-4 inline-block rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-700 ring-1 ring-teal-200">
            Retrieval-Augmented Generation · Educational Demo
          </span>
          <h1 className="text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
            Ask questions. Find evidence. Understand research.
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-slate-600">
            MedRAG-X retrieves the most relevant passages from documents you provide, then uses a large language
            model to generate answers grounded in that evidence — with every claim linked back to its source.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/demo" className="btn-primary">
              Try Demo →
            </Link>
            <Link href="/how-it-works" className="btn-secondary">
              How It Works
            </Link>
          </div>
        </div>

        {/* Pipeline visual */}
        <div className="mt-14 grid gap-3 sm:grid-cols-5">
          {pipelineSteps.map((step, i) => (
            <div key={step.label} className="card p-4">
              <div className="mb-2 flex items-center gap-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-teal-600 text-xs font-bold text-white">
                  {i + 1}
                </span>
                <span className="text-sm font-semibold text-slate-900">{step.label}</span>
              </div>
              <p className="text-xs leading-relaxed text-slate-500">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Feature trio */}
      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 md:grid-cols-3">
          <div>
            <h3 className="font-semibold text-slate-900">Real retrieval, not canned answers</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              Every demo question runs the full pipeline: document chunking, embeddings, vector search, and grounded
              generation. No hardcoded responses anywhere.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Honest about uncertainty</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              When your documents don&apos;t contain the answer, MedRAG-X says so instead of inventing facts or
              fabricating citations.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Open the hood</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              A built-in Technical Details view shows the retrieved chunks, similarity scores, and the exact context
              sent to the model.
            </p>
          </div>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm leading-relaxed text-amber-900">
          <p className="font-semibold">Healthcare disclaimer</p>
          <p className="mt-1">{HEALTH_DISCLAIMER}</p>
        </div>
      </section>
    </div>
  );
}
