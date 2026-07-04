"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE } from "./api-base";
import { CHAR_TAGS, THEME_POOL, langName, pickThemeSuggestions, useLang, useT } from "./i18n";

const CHARACTERS = [
  { id: "sayori", name: "Sayori", letter: "S" },
  { id: "natsuki", name: "Natsuki", letter: "N" },
  { id: "yuri", name: "Yuri", letter: "Y" },
  { id: "monika", name: "Monika", letter: "M" },
] as const;

type Asset = { id: number; status: string; url: string | null; lang?: string };

type ModelInfo = { name: string; label: string; type: string };

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

const TERMINAL = new Set(["done", "failed"]);

// How many random theme chips to surface at once.
const SUGGESTION_COUNT = 10;

export default function Home() {
  const { lang } = useLang();
  const t = useT();
  const [character, setCharacter] = useState<string>("monika");
  const [theme, setTheme] = useState("");
  const [genImage, setGenImage] = useState(true);
  const [genAudio, setGenAudio] = useState(true);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [model, setModel] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [poem, setPoem] = useState<Poem | null>(null);
  // Which language the result card shows. Follows the global mode, but can be
  // toggled per-poem to compare translations while reading.
  const [viewLang, setViewLang] = useState<string>(lang);
  // Languages the active TTS backend can voice (#89). Defaults to English only,
  // matching the default Piper/CPU backend, until the API answers.
  const [ttsLangs, setTtsLangs] = useState<string[]>(["en"]);
  const poemRef = useRef<HTMLElement>(null);

  // Theme example chips: a random handful drawn from the DDLC poem-word pool.
  // Seeded with a deterministic slice so server and client render the same markup
  // (no hydration flash); randomized in the effect below once we're on the client.
  const [suggestions, setSuggestions] = useState<string[]>(() =>
    THEME_POOL[lang].slice(0, SUGGESTION_COUNT),
  );
  // Chips are multi-select: the set of picked suggestions, composed into `theme`.
  const [selected, setSelected] = useState<string[]>([]);

  // Keep the result card in step with the global mode when it changes.
  useEffect(() => {
    setViewLang(lang);
  }, [lang]);

  // Re-roll the suggestion chips on mount and whenever the language switches.
  // The visible chips change, so drop any stale selection highlight (the text
  // already typed into the theme field is left untouched).
  useEffect(() => {
    setSuggestions(pickThemeSuggestions(lang, SUGGESTION_COUNT));
    setSelected([]);
  }, [lang]);

  // Toggle a suggestion in/out of the selection and recompose the theme field
  // from the picks, joined for the active language.
  function toggleSuggestion(s: string) {
    const next = selected.includes(s)
      ? selected.filter((x) => x !== s)
      : [...selected, s];
    setSelected(next);
    setTheme(next.join(lang === "ja" ? "、" : ", "));
  }

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

  // Ask the API which languages can produce audio so we can warn when the active
  // mode's language can't be voiced (e.g. ja on Piper) instead of silently
  // queuing a doomed job (#89).
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

  // Audio is produced in the active mode's language; only possible when the TTS
  // backend can voice it.
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
      setViewLang(lang);
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

  // Bring a newly generated poem into view (the form stays at the top
  // otherwise). Keyed on the poem id so polling updates don't re-scroll.
  const poemId = poem?.id;
  useEffect(() => {
    if (poemId != null) {
      poemRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [poemId]);

  const image = poem?.images?.[0];

  // The audio matching the currently viewed language (falls back to the first).
  const selectedAudio =
    (poem?.audios ?? []).find((a) => (a.lang ?? "en") === viewLang) ??
    poem?.audios?.[0];

  const displayTitle = poem
    ? viewLang === "ja"
      ? poem.title_ja || poem.title
      : poem.title
    : "";

  return (
    <main className="container">
      <header className="hero">
        <h1>Just Poems.</h1>
        <p className="subtitle">{t("hero.subtitle")}</p>
      </header>

      <form onSubmit={generate} className="form-card">
        <div className="field">
          <div className="label">
            {t("form.character")}
            <span className="opt">{t("form.characterOpt")}</span>
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
                <span className="tag">{CHAR_TAGS[lang][c.id]}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <div className="label">
            {t("form.theme")}
            <span className="opt">{t("form.themeOpt")}</span>
          </div>
          <div className="input-wrap">
            <span className="ico" aria-hidden="true">
              ✎
            </span>
            <input
              type="text"
              value={theme}
              onChange={(e) => {
                // Manual edits take over; drop the chip highlight so it can't
                // misrepresent the (now hand-edited) text.
                setTheme(e.target.value);
                setSelected([]);
              }}
              maxLength={200}
              placeholder={t("form.themePlaceholder")}
            />
          </div>
          <div className="suggestions">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                className="chip"
                aria-pressed={selected.includes(s)}
                onClick={() => toggleSuggestion(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <div className="label">{t("form.generateWhat")}</div>
          <div className="options">
            <div className="opt-row">
              <div className="opt-main">
                <span className="t">{t("form.image")}</span>
                <span className="d">{t("form.imageDesc")}</span>
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
                <label htmlFor="model-select">{t("form.model")}</label>
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
                <span className="t">{t("form.audio")}</span>
                <span className="d">{t("form.audioDesc")}</span>
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
          </div>
          {genAudio && !audioSupported && (
            <p className="audio-unsupported" role="note">
              {t("form.audioUnsupported")}
            </p>
          )}
        </div>

        <button type="submit" className="cta" disabled={loading}>
          {loading ? t("form.submitting") : t("form.submit")}
        </button>
        <p className="foot-note">{t("form.footNote")}</p>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {poem && (
        <article ref={poemRef} className="poem" data-testid="poem" data-char={poem.character}>
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
            {image && (
              <div className="poem-image-col" data-testid="image-area">
                {image.status === "done" && image.url ? (
                  <img src={`${API_BASE}${image.url}`} alt={displayTitle} className="poem-image" />
                ) : image.status === "failed" ? (
                  <div className="img-failed">
                    {t("poem.imageFailed")}
                    <button type="button" onClick={() => generate()}>
                      {t("poem.regenerate")}
                    </button>
                  </div>
                ) : (
                  <div className="img-pending">
                    {t("poem.imagePending")} ({image.status ?? "queued"})
                  </div>
                )}
              </div>
            )}

            <div className="poem-main">
              {(poem.audios?.length ?? 0) > 0 && (
                <div className="audio-area" data-testid="audio-area">
                  <div className="audio-head">
                    <span className="audio-label">
                      🔊 {t("poem.narration")}（{langName(t, selectedAudio?.lang ?? viewLang)}）
                    </span>
                  </div>
                  {selectedAudio?.status === "done" && selectedAudio.url ? (
                    <audio
                      controls
                      data-testid="audio-player"
                      src={`${API_BASE}${selectedAudio.url}`}
                    />
                  ) : selectedAudio?.status === "failed" ? (
                    <div className="audio-failed">{t("poem.audioFailed")}</div>
                  ) : (
                    <div className="audio-pending">
                      {t("poem.audioPending")} ({selectedAudio?.status ?? "queued"})
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
