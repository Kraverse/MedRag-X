import type { NextConfig } from "next";

/**
 * Static export: `next build` emits a fully static `out/` directory served by
 * Cloudflare Pages. All RAG work happens in the FastAPI backend; the frontend
 * is pure UI + API calls.
 */
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
