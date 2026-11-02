import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Dockerfile copies .next/standalone, a self-contained server with only the modules it needs.
  output: "standalone",
};

export default nextConfig;
