// Small pure helpers extracted from page.tsx so the polling / audio-gating logic
// is unit-testable without rendering the whole page (#121). Behaviour is
// identical to the previous inline expressions.

// Asset statuses that are final: once here, there is nothing left to poll for.
export const TERMINAL_STATUSES = new Set(["done", "failed"]);

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}

// True while any asset is still being produced — drives the result card's
// 2-second polling. Empty list => nothing pending.
export function hasPendingAssets(assets: ReadonlyArray<{ status: string }>): boolean {
  return assets.some((a) => !isTerminal(a.status));
}

// Whether the active TTS backend can voice the given language (#89): audio is
// only offered for languages the server reported as supported.
export function canVoiceLang(ttsLangs: readonly string[], lang: string): boolean {
  return ttsLangs.includes(lang);
}
