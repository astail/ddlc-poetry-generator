// Resolve the API base URL for browser-side fetches.
//
// Empty by default: `/api/*` is proxied to the api service by this server (see
// the rewrite in next.config.mjs), so requests stay same-origin and work
// unchanged over localhost, a LAN IP, a hostname or a public tunnel domain —
// whatever the page itself was loaded from. That also means the api container
// needs no published port and no CORS entry.
//
// Set NEXT_PUBLIC_API_BASE (a build arg — NEXT_PUBLIC_* is baked into the
// bundle) only to bypass the proxy and call an API on another origin; that
// origin then has to allow it via CORS_ALLOW_ORIGINS.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";
