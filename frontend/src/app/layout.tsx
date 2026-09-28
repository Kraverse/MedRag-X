import type { Metadata } from "next";
import Link from "next/link";
import { HEALTH_DISCLAIMER } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedRAG-X — Evidence-Grounded Medical Research Assistant",
  description:
    "MedRAG-X retrieves relevant evidence from documents you provide and generates grounded answers with source citations. Educational research demo — not a medical device.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-center gap-2 font-bold text-slate-900">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-teal-600 text-sm text-white">
                ✚
              </span>
              MedRAG-X
            </Link>
            <nav className="flex items-center gap-5 text-sm text-slate-600">
              <Link href="/how-it-works" className="hover:text-slate-900">
                How It Works
              </Link>
              <Link href="/demo" className="btn-primary !py-1.5 !px-3.5 text-sm">
                Try Demo
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-slate-200 bg-white">
          <div className="mx-auto max-w-6xl px-4 py-6 text-xs leading-relaxed text-slate-500">
            <p className="mb-2 font-medium text-slate-600">{HEALTH_DISCLAIMER}</p>
            <p>
              MedRAG-X · Educational RAG demonstration · Retrieval-Augmented Generation with source citations ·
              <Link href="/how-it-works" className="ml-1 underline hover:text-slate-700">
                How it works
              </Link>
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
