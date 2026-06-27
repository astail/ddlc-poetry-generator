"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type Asset = { status: string; url: string | null; lang?: string };
type Poem = {
  id: number;
  character: string;
  title: string;
  poem_en: string;
  poem_ja: string;
  mood?: string | null;
  images: Asset[];
  audios: Asset[];
};

export default function PoemDetailPage() {
  const params = useParams();
  const id = Array.isArray(params?.id) ? params?.id[0] : params?.id;
  const [poem, setPoem] = useState<Poem | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/poems/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((d) => setPoem(d as Poem))
      .catch(() => setNotFound(true));
  }, [id]);

  if (notFound) {
    return (
      <main className="container">
        <p className="error">Poem not found.</p>
      </main>
    );
  }
  if (!poem) {
    return (
      <main className="container">
        <p>Loading…</p>
      </main>
    );
  }

  const image = poem.images?.[0];
  const audio = poem.audios?.[0];

  return (
    <main className="container">
      <article className="poem" data-testid="poem">
        <h2>
          {poem.title} <small>— {poem.character}</small>
        </h2>

        <div className="image-area">
          {image?.status === "done" && image.url ? (
            <img src={`${API_BASE}${image.url}`} alt={poem.title} className="poem-image" />
          ) : (
            <div className="img-pending">画像: {image?.status ?? "-"}</div>
          )}
        </div>

        <div className="audio-area">
          {audio?.status === "done" && audio.url ? (
            <audio controls src={`${API_BASE}${audio.url}`} />
          ) : (
            <div className="audio-pending">音声: {audio?.status ?? "-"}</div>
          )}
        </div>

        <pre className="poem-text">{poem.poem_en}</pre>
        <pre className="poem-text poem-ja">{poem.poem_ja}</pre>
      </article>
    </main>
  );
}
