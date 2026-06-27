"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const CHARACTERS = ["sayori", "natsuki", "yuri", "monika"] as const;

type Asset = { id: number; status: string; url: string | null; lang?: string };

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

const TERMINAL = new Set(["done", "failed"]);

export default function Home() {
  const [character, setCharacter] = useState<string>("monika");
  const [theme, setTheme] = useState("");
  const [lang, setLang] = useState("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [poem, setPoem] = useState<Poem | null>(null);
  const [audioLang, setAudioLang] = useState<string | null>(null);

  async function generate(e?: React.FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    setPoem(null);
    setAudioLang(null);
    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character, theme: theme || null, lang }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setPoem((await res.json()) as Poem);
    } catch (err) {
      setError(err instanceof Error ? err.message : "request failed");
    } finally {
      setLoading(false);
    }
  }

  // Poll until both the image and the audio are ready (or failed).
  useEffect(() => {
    if (!poem) return;
    const pending = [...poem.images, ...poem.audios].some(
      (a) => !TERMINAL.has(a.status),
    );
    if (!pending) return;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/poems/${poem.id}`);
        if (res.ok) setPoem((await res.json()) as Poem);
      } catch {
        /* keep state; retry next tick */
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [poem]);

  const image = poem?.images?.[0];

  const audioLangs = useMemo(
    () => Array.from(new Set((poem?.audios ?? []).map((a) => a.lang ?? "en"))),
    [poem],
  );
  const selectedAudio =
    (poem?.audios ?? []).find((a) => (a.lang ?? "en") === audioLang) ??
    poem?.audios?.[0];

  return (
    <main className="container">
      <h1>DDLC Poetry Generator</h1>
      <p className="subtitle">unofficial · non-commercial fan project</p>

      <form onSubmit={generate} className="form">
        <label>
          Character
          <select value={character} onChange={(e) => setCharacter(e.target.value)}>
            {CHARACTERS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label>
          Theme (optional)
          <input
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            maxLength={200}
            placeholder="e.g. the sea at midnight"
          />
        </label>

        <label>
          Language
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="en">English</option>
            <option value="ja">日本語</option>
          </select>
        </label>

        <button type="submit" disabled={loading}>
          {loading ? "Generating…" : "Generate"}
        </button>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {poem && (
        <article className="poem" data-testid="poem">
          <h2>
            {poem.title} <small>— {poem.character}</small>
          </h2>

          <div className="image-area" data-testid="image-area">
            {image?.status === "done" && image.url ? (
              <img src={`${API_BASE}${image.url}`} alt={poem.title} className="poem-image" />
            ) : image?.status === "failed" ? (
              <div className="img-failed">
                画像生成に失敗しました
                <button type="button" onClick={() => generate()}>
                  再生成
                </button>
              </div>
            ) : (
              <div className="img-pending">画像を生成中… ({image?.status ?? "queued"})</div>
            )}
          </div>

          <div className="audio-area" data-testid="audio-area">
            {audioLangs.length > 1 && (
              <div className="audio-langs">
                {audioLangs.map((l) => (
                  <button
                    key={l}
                    type="button"
                    className={l === (audioLang ?? audioLangs[0]) ? "active" : ""}
                    onClick={() => setAudioLang(l)}
                  >
                    {l.toUpperCase()}
                  </button>
                ))}
              </div>
            )}
            {selectedAudio?.status === "done" && selectedAudio.url ? (
              <audio
                controls
                data-testid="audio-player"
                src={`${API_BASE}${selectedAudio.url}`}
              />
            ) : selectedAudio?.status === "failed" ? (
              <div className="audio-failed">音声生成に失敗しました</div>
            ) : (
              <div className="audio-pending">
                音声を生成中… ({selectedAudio?.status ?? "queued"})
              </div>
            )}
          </div>

          <pre className="poem-text">{poem.poem_en}</pre>
          <pre className="poem-text poem-ja">{poem.poem_ja}</pre>
        </article>
      )}
    </main>
  );
}
