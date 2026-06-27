"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const FILTERS: ReadonlyArray<readonly [string, string]> = [
  ["", "All"],
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
  image_status: string | null;
  image_url: string | null;
};

export default function Gallery() {
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

  return (
    <main className="container">
      <h1>Gallery</h1>

      <div className="filters">
        {FILTERS.map(([value, label]) => (
          <button
            key={value || "all"}
            type="button"
            className={value === character ? "active" : ""}
            onClick={() => {
              setCharacter(value);
              setPage(0);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : items.length === 0 ? (
        <p>まだ詩がありません。</p>
      ) : (
        <div className="gallery-grid">
          {items.map((p) => (
            <Link key={p.id} href={`/poems/${p.id}`} className="card">
              {p.image_status === "done" && p.image_url ? (
                <img src={`${API_BASE}${p.image_url}`} alt={p.title} />
              ) : (
                <div className="card-noimg">no image</div>
              )}
              <div className="card-body">
                <strong>{p.title}</strong>
                <span>{p.character}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="pager">
        <button type="button" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
          ← Prev
        </button>
        <span>page {page + 1}</span>
        <button type="button" disabled={items.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
          Next →
        </button>
      </div>
    </main>
  );
}
