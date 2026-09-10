import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import de from "./locales/de.json";
import pt from "./locales/pt.json";
import it from "./locales/it.json";
import ja from "./locales/ja.json";
import ko from "./locales/ko.json";
import zh from "./locales/zh.json";

export const LANGUAGES = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "es", label: "Español", flag: "🇪🇸" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "pt", label: "Português", flag: "🇧🇷" },
  { code: "it", label: "Italiano", flag: "🇮🇹" },
  { code: "ja", label: "日本語", flag: "🇯🇵" },
  { code: "ko", label: "한국어", flag: "🇰🇷" },
  { code: "zh", label: "中文", flag: "🇨🇳" },
];

const CODES = LANGUAGES.map((l) => l.code);
export const normalizeLang = (raw) => {
  const base = (raw || "").toLowerCase().split("-")[0];
  return CODES.includes(base) ? base : "en";
};

const initial = localStorage.getItem("hom_lang") || normalizeLang(navigator.language);

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, es: { translation: es }, fr: { translation: fr }, de: { translation: de }, pt: { translation: pt }, it: { translation: it }, ja: { translation: ja }, ko: { translation: ko }, zh: { translation: zh } },
  lng: normalizeLang(initial),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (lng) => {
  localStorage.setItem("hom_lang", lng);
  document.documentElement.lang = lng;
});

export default i18n;
