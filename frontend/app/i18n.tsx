"use client";

// Global EN / 日本語 mode. One switch (in the nav) drives every UI label plus the
// language of generated content (poem title, poem body, and audio). The choice
// is persisted in localStorage so it survives reloads and navigation.

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { DEFAULT_LANG, LANG_COOKIE, type Lang } from "./i18n-config";

export type { Lang };

type LangCtx = { lang: Lang; setLang: (l: Lang) => void };

const Ctx = createContext<LangCtx>({ lang: DEFAULT_LANG, setLang: () => {} });

export function LangProvider({
  children,
  initialLang,
}: {
  children: React.ReactNode;
  initialLang: Lang;
}) {
  // Seeded from the cookie the server already read, so the first client render
  // matches the server (correct <html lang> + metadata, no hydration flash).
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    // Persist in a cookie so the next server render picks the right language
    // (a year's max-age; lax so it rides top-level navigations).
    try {
      document.cookie = `${LANG_COOKIE}=${l}; path=/; max-age=31536000; samesite=lax`;
    } catch {
      /* best-effort persistence */
    }
    document.documentElement.lang = l;
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

// A pool of theme words drawn from DDLC's poem-writing minigame, spanning the
// girls' preferences: Sayori (warmth / emotion / weather), Yuri (fantasy &
// unsettling), Natsuki (cute & simple), plus a few Monika-ish meta touches. The
// two arrays are strictly index-aligned. We show a random handful each visit so
// the suggestions feel fresh — echoing the word-picking game the app is built on.
// (Sourced from the DDLC+ poem word list; the most graphic words are omitted.)
export const THEME_POOL: Record<Lang, string[]> = {
  ja: [
    // Sayori-ish: warmth, emotion, weather
    "バラ", "蛍", "花火", "虹", "海", "夕焼け", "陽だまり", "花", "音楽", "冒険",
    "宝物", "思い出", "幸せ", "希望", "笑顔", "親友", "約束", "抱擁", "温もり", "幼い日",
    // Yuri-ish: fantasy, longing, the unsettling
    "白昼夢", "涙", "悲しみ", "孤独", "夢", "幻想", "檻", "憂鬱", "執着", "深紅",
    "永遠", "無限", "宇宙", "運命", "旋風", "渇望", "星空", "月明かり", "雨", "雨雲",
    "風景", "肖像", "苦悶", "絶望", "恐怖", "悪夢", "不安", "ナイフ", "片想い", "沈黙",
    // Natsuki-ish: cute & simple
    "リボン", "パフェ", "いちご", "ピンク", "バニラ", "キャンディ", "マシュマロ", "チョコレート", "カップケーキ", "うさぎ",
    "子猫", "子犬", "かわいい", "ふわふわ", "きらめき", "どきどき", "メロディー", "しゃぼん玉", "砂糖", "夏",
    // Monika-ish / club atmosphere
    "パステル", "放課後の教室", "文芸部", "現実の裂け目",
  ],
  en: [
    "Rose", "Firefly", "Fireworks", "Rainbow", "Sea", "Sunset", "Sunshine", "Flower", "Music", "Adventure",
    "Treasure", "Memory", "Happiness", "Hope", "Smile", "Best friends", "A promise", "Embrace", "Warmth", "Childhood",
    "Daydream", "Tears", "Sorrow", "Loneliness", "Dream", "Fantasy", "A cage", "Melancholy", "Obsession", "Crimson",
    "Eternity", "Infinity", "The universe", "Fate", "Whirlwind", "Craving", "Starry sky", "Moonlight", "Rain", "Rain cloud",
    "Scenery", "A portrait", "Agony", "Despair", "Horror", "Nightmare", "Anxiety", "A knife", "Unrequited love", "Silence",
    "Ribbon", "Parfait", "Strawberry", "Pink", "Vanilla", "Candy", "Marshmallow", "Chocolate", "Cupcakes", "Rabbit",
    "Kitten", "Puppy", "Cute", "Fluffy", "Sparkle", "Doki-doki", "Melody", "Bubbles", "Sugar", "Summer",
    "Pastel colors", "After-school classroom", "Literature club", "A crack in reality",
  ],
};

// Pick `n` distinct random themes for the given language. Called on the client
// (in an effect) so each visit surfaces a different set of chips.
export function pickThemeSuggestions(lang: Lang, n = 5): string[] {
  const pool = THEME_POOL[lang];
  const used = new Set<number>();
  const picked: string[] = [];
  const count = Math.min(n, pool.length);
  while (picked.length < count) {
    const i = Math.floor(Math.random() * pool.length);
    if (used.has(i)) continue;
    used.add(i);
    picked.push(pool[i]);
  }
  return picked;
}

// Human-readable name of a content language, expressed in the active UI language.
export function langName(t: (k: StringKey) => string, contentLang: string): string {
  return contentLang === "ja" ? t("poem.langJa") : t("poem.langEn");
}
