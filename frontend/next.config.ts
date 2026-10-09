import type { NextConfig } from "next";

// A fixed operator-configured upstream keeps cookies on the web application's
// origin. Rewrites are compiled during the build; changing it requires a rebuild.
const apiProxyOrigin = process.env.API_PROXY_ORIGIN?.trim();
if (apiProxyOrigin) {
  const upstream = new URL(apiProxyOrigin);
  const localHttp = upstream.protocol === "http:" &&
    ["localhost", "127.0.0.1"].includes(upstream.hostname);
  if ((upstream.protocol !== "https:" && !localHttp) || upstream.username ||
      upstream.password || upstream.pathname !== "/" || upstream.search || upstream.hash) {
    throw new Error("API_PROXY_ORIGIN must be an HTTPS origin without credentials, path or query");
  }
}

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return apiProxyOrigin ? [{
      source: "/api/:path*",
      destination: `${new URL(apiProxyOrigin).origin}/api/:path*`,
    }] : [];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    root: process.cwd(),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
