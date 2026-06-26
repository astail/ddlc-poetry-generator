"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const CHARACTERS = ["sayori", "natsuki", "yuri", "monika"] as const;

type Poem = {
  id: number;
  character: string;
  title: string;
  poem_en: string;
  poem_ja: string;
  mood?: string | null;
  image_status: string;
  audio_status: string;
};

export default function Home() {
  const [character, setCharacter] = useState<string>("monika");
  const [theme, setTheme] = useState("");
  const [lang, setLang] = useState("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [poem, setPoem] = useState<Poem | null>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setPoem(null);
    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character, theme: theme || null, lang }),
      });
      if (!res.ok) {
        throw new Error(`API error ${res.status}`);
      }
      setPoem((await res.json()) as Poem);
    } catch (err) {
      setError(err instanceof Error ? err.message : "request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <h1>DDLC Poetry Generator</h1>
      <p className="subtitle">unofficial · non-commercial fan project</p>

      <form onSubmit={generate} className="form">
        <label>
          Character
          <select
            value={character}
            onChange={(e) => setCharacter(e.target.value)}
          >
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
          <pre className="poem-text">{poem.poem_en}</pre>
          <pre className="poem-text poem-ja">{poem.poem_ja}</pre>
          <p className="status">
            image: {poem.image_status} · audio: {poem.audio_status}
          </p>
        </article>
      )}
    </main>
  );
}
