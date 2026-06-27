// Resolve the API base URL for browser-side fetches.
//
// A baked-in NEXT_PUBLIC_API_BASE (set as a build arg) always wins. Otherwise
// we derive the base from the host the page was actually loaded from, so that
// LAN access (e.g. http://192.168.10.200:3000) reaches the API on that same
// host instead of the visitor's own "localhost". Falls back to localhost during
// server-side rendering, where `window` is undefined.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:${
        process.env.NEXT_PUBLIC_API_PORT ?? "8000"
      }`
    : "http://localhost:8000");
