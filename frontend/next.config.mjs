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

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Next 16 removed build-time ESLint integration (and `next lint`); linting is
  // a separate step (`npm run lint` -> `eslint .`, run in CI).
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
