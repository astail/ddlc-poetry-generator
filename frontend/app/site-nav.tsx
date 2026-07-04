"use client";

import Link from "next/link";

import { useLang, useT } from "./i18n";

export default function SiteNav() {
  const { lang, setLang } = useLang();
  const t = useT();
  return (
    <nav className="nav">
      <Link href="/">{t("nav.generate")}</Link>
      <Link href="/gallery">{t("nav.gallery")}</Link>
      <div className="lang-switch" role="group" aria-label="Language / 言語">
        <button
          type="button"
          className={lang === "en" ? "active" : ""}
          aria-pressed={lang === "en"}
          onClick={() => setLang("en")}
        >
          EN
        </button>
        <button
          type="button"
          className={lang === "ja" ? "active" : ""}
          aria-pressed={lang === "ja"}
          onClick={() => setLang("ja")}
        >
          日本語
        </button>
      </div>
    </nav>
  );
}
