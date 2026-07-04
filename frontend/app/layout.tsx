import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { LANG_COOKIE, resolveLang } from "./i18n-config";
import { LangProvider } from "./i18n";
import SiteNav from "./site-nav";

// Reading the cookie makes rendering dynamic (per-request), which is what we
// want: the language is a user preference, not a build-time constant.
export function generateMetadata(): Metadata {
  const lang = resolveLang(cookies().get(LANG_COOKIE)?.value);
  return lang === "ja"
    ? {
        title: "Just Poems",
        description: "非公式・非営利の DDLC ファン詩ジェネレーター",
      }
    : {
        title: "Just Poems",
        description: "Unofficial, non-commercial DDLC fan poem generator",
      };
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const lang = resolveLang(cookies().get(LANG_COOKIE)?.value);
  return (
    <html lang={lang}>
      <body>
        <LangProvider initialLang={lang}>
          <SiteNav />
          {children}
        </LangProvider>
      </body>
    </html>
  );
}
