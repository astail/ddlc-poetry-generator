// Locale config shared by Server Components (layout / metadata) and the client
// LangProvider. Deliberately free of "use client" so the server can import
// resolveLang to render the correct <html lang> and localized metadata.

export type Lang = "en" | "ja";

export const LANG_COOKIE = "ddlc-lang";
export const DEFAULT_LANG: Lang = "ja";

export function resolveLang(value: string | null | undefined): Lang {
  return value === "en" || value === "ja" ? value : DEFAULT_LANG;
}
