"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { API_BASE } from "../../api-base";
import { langName, useLang, useT } from "../../i18n";

type Asset = { status: string; url: string | null; lang?: string };
type Poem = {
  id: number;
  character: string;
  title: string;
  title_ja?: string | null;
  poem_en: string;
  poem_ja: string;
  mood?: string | null;
  images: Asset[];
  audios: Asset[];
};

export default function PoemDetailPage() {
  const params = useParams();
  const id = Array.isArray(params?.id) ? params?.id[0] : params?.id;
  const { lang } = useLang();
  const t = useT();
  const [poem, setPoem] = useState<Poem | null>(null);
  const [notFound, setNotFound] = useState(false);
  // Language shown in the result card. Follows the global mode, but can be
  // toggled per-poem to compare translations.
  const [viewLang, setViewLang] = useState<string>(lang);

  useEffect(() => {
    setViewLang(lang);
  }, [lang]);

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
        <p className="error">{t("detail.notFound")}</p>
      </main>
    );
  }
  if (!poem) {
    return (
      <main className="container">
        <p>{t("detail.loading")}</p>
      </main>
    );
  }

  const image = poem.images?.[0];
  const selectedAudio =
    poem.audios?.find((a) => (a.lang ?? "en") === viewLang) ?? poem.audios?.[0];
  const displayTitle =
    viewLang === "ja" ? poem.title_ja || poem.title : poem.title;

  return (
    <main className="container">
      <article className="poem" data-testid="poem" data-char={poem.character}>
        <div className="poem-head">
          <span className="poem-avatar" aria-hidden="true">
            {poem.character.charAt(0).toUpperCase()}
          </span>
          <div className="poem-heading">
            <h2 className="poem-title">{displayTitle}</h2>
            <div className="poem-by">
              {poem.character}
              {poem.mood ? ` · ${poem.mood}` : ""}
            </div>
          </div>
          <div className="lang-toggle" role="group" aria-label={t("poem.langGroup")}>
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
          {(image || (poem.audios?.length ?? 0) > 0) && (
            <div className="poem-pinned">
              {(poem.audios?.length ?? 0) > 0 && (
                <div className="audio-area">
                  <div className="audio-head">
                    <span className="audio-label">
                      🔊 {t("poem.narration")}（{langName(t, selectedAudio?.lang ?? viewLang)}）
                    </span>
                  </div>
                  {selectedAudio?.status === "done" && selectedAudio.url ? (
                    <audio controls src={`${API_BASE}${selectedAudio.url}`} />
                  ) : (
                    <div className="audio-pending">
                      {t("poem.audio")}: {selectedAudio?.status ?? "-"}
                    </div>
                  )}
                </div>
              )}

              {image && (
                <div className="poem-image-col">
                  {image.status === "done" && image.url ? (
                    <img src={`${API_BASE}${image.url}`} alt={displayTitle} className="poem-image" />
                  ) : (
                    <div className="img-pending">
                      {t("poem.image")}: {image.status ?? "-"}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="poem-main">
            <pre className="poem-text poem-en" hidden={viewLang !== "en"}>{poem.poem_en}</pre>
            <pre className="poem-text poem-ja" hidden={viewLang !== "ja"}>{poem.poem_ja}</pre>
          </div>
        </div>
      </article>
    </main>
  );
}
