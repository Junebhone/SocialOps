import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `next build` emits .next/standalone: a server.js plus only the node_modules
  // it traces as used. The runtime image copies that instead of the full
  // dependency tree (web/Dockerfile, D33). `next dev` ignores this setting.
  output: "standalone",
};

export default nextConfig;
