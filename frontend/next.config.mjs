// Security response headers applied to every route (#118). Kept deliberately
// safe for this app: nosniff / frame-options / referrer / permissions, plus a
// minimal CSP that only hardens framing, base-uri and plugins — it does NOT
// restrict script/style/connect, so it can't break Next's inline hydration or
// the cross-origin fetches to the API (whose port is derived at runtime).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
  },
];

// The browser calls the API through this server: `/api/*` is proxied to the api
// service, so the page and its API share one origin (no CORS, and no API port
// that has to be published on the host). The destination is a *name* — the
// docker compose service (`http://api:8000`) — so it survives container
// restarts and IP churn.
//
// NOTE: `next build` evaluates rewrites() and writes the result into
// .next/routes-manifest.json, so API_ORIGIN is read at BUILD time (like
// NEXT_PUBLIC_*), not when the standalone server boots. compose passes it as a
// build arg; changing it needs `docker compose up --build`.
const apiOrigin = process.env.API_ORIGIN || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Next 16 removed build-time ESLint integration (and `next lint`); linting is
  // a separate step (`npm run lint` -> `eslint .`, run in CI).
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
