"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { API_BASE } from "../../api-base";

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
  // Language shown in the result card. Defaults to the existing audio's
  // language (what was chosen at generation), otherwise Japanese.
  const [viewLang, setViewLang] = useState<string>("ja");

  useEffect(() => {
    if (!id) return;
    fetch(`${API_BASE}/api/poems/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((d) => {
        const p = d as Poem;
        setViewLang(p.audios?.[0] ? (p.audios[0].lang ?? "en") : "ja");
        setPoem(p);
      })
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
  const selectedAudio =
    poem.audios?.find((a) => (a.lang ?? "en") === viewLang) ?? poem.audios?.[0];

  return (
    <main className="container">
      <article className="poem" data-testid="poem" data-char={poem.character}>
        <div className="poem-head">
          <span className="poem-avatar" aria-hidden="true">
            {poem.character.charAt(0).toUpperCase()}
          </span>
          <div className="poem-heading">
            <h2 className="poem-title">{poem.title}</h2>
            <div className="poem-by">
              {poem.character}
              {poem.mood ? ` · ${poem.mood}` : ""}
            </div>
          </div>
          <div className="lang-toggle" role="group" aria-label="詩の言語">
            <button
              type="button"
              className={viewLang === "en" ? "active" : ""}
              onClick={() => setViewLang("en")}
            >
              EN
            </button>
            <button
              type="button"
              className={viewLang === "ja" ? "active" : ""}
              onClick={() => setViewLang("ja")}
            >
              日本語
            </button>
          </div>
        </div>

        <div className={`poem-inner${image ? "" : " no-image"}`}>
          {image && (
            <div className="poem-image-col">
              {image.status === "done" && image.url ? (
                <img src={`${API_BASE}${image.url}`} alt={poem.title} className="poem-image" />
              ) : (
                <div className="img-pending">画像: {image.status ?? "-"}</div>
              )}
            </div>
          )}

          <div className="poem-main">
            {(poem.audios?.length ?? 0) > 0 && (
              <div className="audio-area">
                <div className="audio-head">
                  <span className="audio-label">
                    🔊 読み上げ（{viewLang === "ja" ? "日本語" : "English"}）
                  </span>
                </div>
                {selectedAudio?.status === "done" && selectedAudio.url ? (
                  <audio controls src={`${API_BASE}${selectedAudio.url}`} />
                ) : (
                  <div className="audio-pending">音声: {selectedAudio?.status ?? "-"}</div>
                )}
              </div>
            )}

            <pre className="poem-text poem-en" hidden={viewLang !== "en"}>{poem.poem_en}</pre>
            <pre className="poem-text poem-ja" hidden={viewLang !== "ja"}>{poem.poem_ja}</pre>
          </div>
        </div>
      </article>
    </main>
  );
}
