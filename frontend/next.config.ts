import type { NextConfig } from "next";

const config: NextConfig = {
  agentRules: false,
  poweredByHeader: false,
  output: "standalone",
  async rewrites() {
    const api = (process.env.API_INTERNAL_URL || process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "X-Frame-Options", value: "DENY" }
      ]
    }];
  },
};

export default config;
