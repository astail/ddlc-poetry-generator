"use client";

// Global EN / 日本語 mode. One switch (in the nav) drives every UI label plus the
// language of generated content (poem title, poem body, and audio). The choice
// is persisted in localStorage so it survives reloads and navigation.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Lang = "en" | "ja";

const STORAGE_KEY = "ddlc-lang";

type LangCtx = { lang: Lang; setLang: (l: Lang) => void };

const Ctx = createContext<LangCtx>({ lang: "ja", setLang: () => {} });

export function LangProvider({ children }: { children: React.ReactNode }) {
  // Japanese is the default (server render + first client render both use it, so
  // there's no hydration mismatch). A persisted choice is applied after mount.
  const [lang, setLangState] = useState<Lang>("ja");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "ja") setLangState(saved);
    } catch {
      /* localStorage unavailable (private mode): keep the default */
    }
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* best-effort persistence */
    }
  }, []);

  const value = useMemo(() => ({ lang, setLang }), [lang, setLang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLang() {
  return useContext(Ctx);
}

// ------------------------------------------------------------------ dictionary
const STRINGS = {
  ja: {
    "nav.generate": "生成",
    "nav.gallery": "ギャラリー",
    "hero.subtitle": "非公式・非営利のファン制作物",
    "form.character": "キャラクター",
    "form.characterOpt": "作風を選ぶ",
    "form.theme": "テーマ",
    "form.themeOpt": "任意 — 空欄でおまかせ",
    "form.themePlaceholder": "例: 真夜中の海",
    "form.generateWhat": "生成するもの",
    "form.image": "🎨 画像を生成",
    "form.imageDesc": "詩の雰囲気に合わせたイラスト",
    "form.model": "モデル",
    "form.audio": "🔊 音声を生成",
    "form.audioDesc": "キャラボイス風に読み上げ",
    "form.audioUnsupported":
      "※ 日本語の音声生成は、現在のサーバ構成では利用できません。日本語の読み上げにはサーバ側で VOICEVOX を有効化してください（英語は利用できます）。",
    "form.submit": "✨ 生成する",
    "form.submitting": "生成中…",
    "form.footNote": "Team Salvato とは無関係の非公式ファン制作物です",
    "poem.narration": "読み上げ",
    "poem.langGroup": "詩の言語",
    "poem.langEn": "英語",
    "poem.langJa": "日本語",
    "poem.imageFailed": "画像生成に失敗しました",
    "poem.regenerate": "再生成",
    "poem.imagePending": "画像を生成中…",
    "poem.audioFailed": "音声生成に失敗しました",
    "poem.audioPending": "音声を生成中…",
    "poem.image": "画像",
    "poem.audio": "音声",
    "gallery.title": "ギャラリー",
    "gallery.subtitle": "これまでに生まれた詩",
    "gallery.all": "すべて",
    "gallery.loading": "読み込み中…",
    "gallery.empty": "まだ詩がありません。",
    "gallery.noImage": "画像なし",
    "gallery.prev": "← 前へ",
    "gallery.next": "次へ →",
    "gallery.page": "ページ",
    "detail.notFound": "詩が見つかりません。",
    "detail.loading": "読み込み中…",
  },
  en: {
    "nav.generate": "Generate",
    "nav.gallery": "Gallery",
    "hero.subtitle": "unofficial · non-commercial fan project",
    "form.character": "Character",
    "form.characterOpt": "pick a style",
    "form.theme": "Theme",
    "form.themeOpt": "optional — leave blank for a surprise",
    "form.themePlaceholder": "e.g. Midnight sea",
    "form.generateWhat": "What to create",
    "form.image": "🎨 Generate image",
    "form.imageDesc": "An illustration matching the poem's mood",
    "form.model": "Model",
    "form.audio": "🔊 Generate audio",
    "form.audioDesc": "Read aloud, character-voice style",
    "form.audioUnsupported":
      "※ Japanese audio isn't available in the current server setup. Enable VOICEVOX on the server for Japanese narration (English works).",
    "form.submit": "✨ Generate",
    "form.submitting": "Generating…",
    "form.footNote": "An unofficial fan work, not affiliated with Team Salvato.",
    "poem.narration": "Narration",
    "poem.langGroup": "Poem language",
    "poem.langEn": "English",
    "poem.langJa": "Japanese",
    "poem.imageFailed": "Image generation failed",
    "poem.regenerate": "Regenerate",
    "poem.imagePending": "Generating image…",
    "poem.audioFailed": "Audio generation failed",
    "poem.audioPending": "Generating audio…",
    "poem.image": "Image",
    "poem.audio": "Audio",
    "gallery.title": "Gallery",
    "gallery.subtitle": "Poems created so far",
    "gallery.all": "All",
    "gallery.loading": "Loading…",
    "gallery.empty": "No poems yet.",
    "gallery.noImage": "no image",
    "gallery.prev": "← Prev",
    "gallery.next": "Next →",
    "gallery.page": "Page",
    "detail.notFound": "Poem not found.",
    "detail.loading": "Loading…",
  },
} as const;

export type StringKey = keyof (typeof STRINGS)["ja"];

export function useT() {
  const { lang } = useLang();
  return useCallback((key: StringKey) => STRINGS[lang][key], [lang]);
}

// Content that isn't a single label: character style tags and theme chips are
// authored per language so the whole page reads in one voice.
export const CHAR_TAGS: Record<Lang, Record<string, string>> = {
  ja: {
    sayori: "明るい・素朴",
    natsuki: "元気・率直",
    yuri: "耽美・幻想",
    monika: "知的・内省",
  },
  en: {
    sayori: "cheerful · plain",
    natsuki: "spirited · blunt",
    yuri: "aesthetic · dreamy",
    monika: "intellectual · introspective",
  },
};

export const THEME_SUGGESTIONS: Record<Lang, string[]> = {
  ja: ["真夜中の海", "放課後の教室", "桜", "雨と紅茶", "遠い約束"],
  en: ["Midnight sea", "After-school classroom", "Cherry blossoms", "Rain and tea", "A distant promise"],
};

// Human-readable name of a content language, expressed in the active UI language.
export function langName(t: (k: StringKey) => string, contentLang: string): string {
  return contentLang === "ja" ? t("poem.langJa") : t("poem.langEn");
}
