import type { NextConfig } from "next";

// NEXT_OUTPUT=export builds a static site (frontend/out) that the FastAPI
// backend serves itself in the Docker image. Local `npm run dev` is unaffected.
const staticExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  ...(staticExport && {
    output: "export",
    // /login -> /login/index.html, which a plain static file server can find.
    trailingSlash: true,
  }),
};

export default nextConfig;
