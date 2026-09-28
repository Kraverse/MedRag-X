import DemoWorkspace from "@/components/DemoWorkspace";

export default function DemoPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">MedRAG-X Demo</h1>
      <p className="mt-2 text-sm text-slate-600">
        Runs the real retrieval pipeline on safe, fully synthetic research documents — no account, no setup.
      </p>
      <div className="mt-8">
        <DemoWorkspace />
      </div>
    </div>
  );
}
