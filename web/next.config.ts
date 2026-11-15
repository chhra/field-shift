import type { NextConfig } from "next";

const API_URL = process.env.FIELD_SHIFT_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Live field analysis (EE + NASA POWER) can take ~60s; default proxy cutoffs look like a blank 500.
  experimental: {
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
