"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { API_BASE } from "../api-base";
import { useLang, useT } from "../i18n";

const FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["", "all"],
  ["sayori", "Sayori"],
  ["natsuki", "Natsuki"],
  ["yuri", "Yuri"],
  ["monika", "Monika"],
];

const PAGE_SIZE = 12;

type Summary = {
  id: number;
  character: string;
  title: string;
  title_ja?: string | null;
  mood?: string | null;
  image_status: string | null;
  image_url: string | null;
};

export default function Gallery() {
  const { lang } = useLang();
  const t = useT();
  const [character, setCharacter] = useState("");
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (character) params.set("character", character);
    fetch(`${API_BASE}/api/poems?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setItems(d as Summary[]))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [character, page]);

  const cardTitle = (p: Summary) =>
    lang === "ja" ? p.title_ja || p.title : p.title;

  return (
    <main className="container">
      <header className="hero">
        <h1>{t("gallery.title")}</h1>
        <p className="subtitle">{t("gallery.subtitle")}</p>
      </header>

      <div className="filters">
        {FILTERS.map(([value, label]) => (
          <button
            key={value || "all"}
            type="button"
            data-char={value}
            className={value === character ? "active" : ""}
            onClick={() => {
              setCharacter(value);
              setPage(0);
            }}
          >
            {label === "all" ? t("gallery.all") : label}
          </button>
        ))}
      </div>

      {loading ? (
        <p>{t("gallery.loading")}</p>
      ) : items.length === 0 ? (
        <p>{t("gallery.empty")}</p>
      ) : (
        <div className="gallery-grid">
          {items.map((p) => (
            <Link key={p.id} href={`/poems/${p.id}`} className="card" data-char={p.character}>
              <div className="card-media">
                {p.image_status === "done" && p.image_url ? (
                  <img src={`${API_BASE}${p.image_url}`} alt={cardTitle(p)} />
                ) : (
                  <div className="card-noimg" role="img" aria-label={t("gallery.noImage")}>
                    🌸
                  </div>
                )}
                <span className="card-char">{p.character}</span>
              </div>
              <div className="card-body">
                <strong>{cardTitle(p)}</strong>
                {p.mood && <span className="card-mood">{p.mood}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="pager">
        <button type="button" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
          {t("gallery.prev")}
        </button>
        <span>
          {t("gallery.page")} {page + 1}
        </span>
        <button type="button" disabled={items.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
          {t("gallery.next")}
        </button>
      </div>
    </main>
  );
}
