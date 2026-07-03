"use client";

import { useEffect, useState } from "react";

import { API_BASE } from "./api-base";

const CHARACTERS = [
  { id: "sayori", name: "Sayori", letter: "S", tag: "明るい・素朴" },
  { id: "natsuki", name: "Natsuki", letter: "N", tag: "元気・率直" },
  { id: "yuri", name: "Yuri", letter: "Y", tag: "耽美・幻想" },
  { id: "monika", name: "Monika", letter: "M", tag: "知的・内省" },
] as const;

const THEME_SUGGESTIONS = ["真夜中の海", "放課後の教室", "桜", "雨と紅茶", "遠い約束"];

type Asset = { id: number; status: string; url: string | null; lang?: string };

type ModelInfo = { name: string; label: string; type: string };

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
  const [genImage, setGenImage] = useState(true);
  const [genAudio, setGenAudio] = useState(true);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [model, setModel] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [poem, setPoem] = useState<Poem | null>(null);
  // Which language the result card shows. Defaults to the chosen audio language
  // when audio is generated, otherwise Japanese (set at generation time).
  const [viewLang, setViewLang] = useState<string>("ja");
  // Languages the active TTS backend can voice (#89). Defaults to English only,
  // matching the default Piper/CPU backend, until the API answers.
  const [ttsLangs, setTtsLangs] = useState<string[]>(["en"]);

  // Load the selectable image models once (#49).
  useEffect(() => {
    fetch(`${API_BASE}/api/models`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setModels(d.models ?? []);
        setModel(d.default ?? "");
      })
      .catch(() => {
        /* dropdown just stays empty; the API uses its default */
      });
  }, []);

  // Ask the API which languages can produce audio so we can disable the option
  // for unsupported ones (e.g. ja on Piper) instead of queuing a doomed job (#89).
  useEffect(() => {
    fetch(`${API_BASE}/api/tts/capabilities`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.langs?.length) setTtsLangs(d.langs);
      })
      .catch(() => {
        /* keep the English-only default; ja audio just stays disabled */
      });
  }, []);

  const audioSupported = ttsLangs.includes(lang);

  async function generate(e?: React.FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    setPoem(null);
    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          character,
          theme: theme || null,
          lang,
          generate_image: genImage,
          // Don't request audio in a language the backend can't voice (#89).
          generate_audio: genAudio && audioSupported,
          model: model || null,
        }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      // Prefer the generated audio's language; fall back to Japanese when no
      // audio was requested (per user preference).
      const willAudio = genAudio && audioSupported;
      setViewLang(willAudio ? lang : "ja");
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

  // The audio matching the currently viewed language (falls back to the first).
  const selectedAudio =
    (poem?.audios ?? []).find((a) => (a.lang ?? "en") === viewLang) ??
    poem?.audios?.[0];

  return (
    <main className="container">
      <header className="hero">
        <h1>詩を、綴ろう。</h1>
        <p className="subtitle">unofficial · non-commercial fan project</p>
      </header>

      <form onSubmit={generate} className="form-card">
        <div className="field">
          <div className="label">
            キャラクター
            <span className="opt">作風を選ぶ</span>
          </div>
          <div className="char-grid">
            {CHARACTERS.map((c) => (
              <button
                key={c.id}
                type="button"
                className="char"
                data-c={c.id}
                aria-pressed={character === c.id}
                onClick={() => setCharacter(c.id)}
              >
                <span className="check" aria-hidden="true">
                  ✓
                </span>
                <span className="avatar" aria-hidden="true">
                  {c.letter}
                </span>
                <span className="name">{c.name}</span>
                <span className="tag">{c.tag}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <div className="label">
            テーマ
            <span className="opt">任意 — 空欄でおまかせ</span>
          </div>
          <div className="input-wrap">
            <span className="ico" aria-hidden="true">
              ✎
            </span>
            <input
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              maxLength={200}
              placeholder="例: 真夜中の海"
            />
          </div>
          <div className="suggestions">
            {THEME_SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => setTheme(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <div className="label">生成するもの</div>
          <div className="options">
            <div className="opt-row">
              <div className="opt-main">
                <span className="t">🎨 画像を生成</span>
                <span className="d">詩の雰囲気に合わせたイラスト</span>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={genImage}
                  onChange={(e) => setGenImage(e.target.checked)}
                />
                <span className="track" />
                <span className="thumb" />
              </label>
            </div>

            {genImage && models.length > 0 && (
              <div className="sub-select">
                <label htmlFor="model-select">モデル</label>
                <select
                  id="model-select"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {models.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="opt-row">
              <div className="opt-main">
                <span className="t">🔊 音声を生成</span>
                <span className="d">キャラボイスで読み上げ</span>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={genAudio}
                  onChange={(e) => setGenAudio(e.target.checked)}
                />
                <span className="track" />
                <span className="thumb" />
              </label>
            </div>

            {genAudio && (
              <div className="sub-select">
                <label htmlFor="voice-lang">音声の言語</label>
                <select
                  id="voice-lang"
                  value={lang}
                  onChange={(e) => setLang(e.target.value)}
                >
                  <option value="en">English（英語）</option>
                  <option value="ja" disabled={!ttsLangs.includes("ja")}>
                    日本語{ttsLangs.includes("ja") ? "" : "（利用不可）"}
                  </option>
                </select>
              </div>
            )}
          </div>
          {genAudio && !ttsLangs.includes("ja") && (
            <p className="audio-unsupported" role="note">
              ※ 日本語の音声生成は、現在のサーバ構成では利用できません。
              日本語の読み上げにはサーバ側で VOICEVOX を有効化してください（英語は利用できます）。
            </p>
          )}
        </div>

        <button type="submit" className="cta" disabled={loading}>
          {loading ? "生成中…" : "✨ 生成する"}
        </button>
        <p className="foot-note">Team Salvato とは無関係の非公式ファン制作物です</p>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {poem && (
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
              <div className="poem-image-col" data-testid="image-area">
                {image.status === "done" && image.url ? (
                  <img src={`${API_BASE}${image.url}`} alt={poem.title} className="poem-image" />
                ) : image.status === "failed" ? (
                  <div className="img-failed">
                    画像生成に失敗しました
                    <button type="button" onClick={() => generate()}>
                      再生成
                    </button>
                  </div>
                ) : (
                  <div className="img-pending">画像を生成中… ({image.status ?? "queued"})</div>
                )}
              </div>
            )}

            <div className="poem-main">
              {(poem.audios?.length ?? 0) > 0 && (
                <div className="audio-area" data-testid="audio-area">
                  <div className="audio-head">
                    <span className="audio-label">
                      🔊 読み上げ（{viewLang === "ja" ? "日本語" : "English"}）
                    </span>
                  </div>
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
              )}

              <pre className="poem-text poem-en" hidden={viewLang !== "en"}>{poem.poem_en}</pre>
              <pre className="poem-text poem-ja" hidden={viewLang !== "ja"}>{poem.poem_ja}</pre>
            </div>
          </div>
        </article>
      )}
    </main>
  );
}
