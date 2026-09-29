import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Do not let Next.js select a lockfile in a parent directory as this
  // project's root. On Windows that made Turbopack scan C:\Users\Dell and
  // crash with "Access is denied".
  turbopack: {
    root: process.cwd(),
  },
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    const backendUrl =
      process.env.DOWNLOADER_BACKEND_URL || "http://127.0.0.1:8001";

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  reactStrictMode: false,
};

export default nextConfig;
