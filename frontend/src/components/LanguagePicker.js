import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Globe, Check } from "lucide-react";
import { LANGUAGES } from "../i18n";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

export function LanguagePicker({ compact = false }) {
  const { i18n, t } = useTranslation();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = LANGUAGES.find((l) => l.code === i18n.language) || LANGUAGES[0];

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (code) => {
    i18n.changeLanguage(code);
    setOpen(false);
    if (user) api.patch("/auth/me", { language: code }).catch(() => {});
  };

  return (
    <div ref={ref} className="relative" data-testid="language-picker">
      <button type="button" data-testid="language-picker-btn" onClick={() => setOpen(!open)} aria-label={t("nav.language")}
        className={`flex items-center gap-1.5 p-2 rounded-sm hover:text-[#CCFF00] transition-colors ${compact ? "" : "label-caps"}`}>
        <Globe size={16} />
        <span className="text-[11px] uppercase font-unbounded" data-testid="language-current">{current.code}</span>
      </button>
      {open && (
        <div data-testid="language-menu" className="absolute right-0 mt-2 w-48 bg-[#121214] border border-white/10 rounded-sm shadow-2xl py-1 z-[80] fade-up">
          <div className="label-caps text-[10px] text-zinc-500 px-3 py-2">{t("nav.language")}</div>
          {LANGUAGES.map((l) => (
            <button key={l.code} type="button" data-testid={`language-option-${l.code}`} onClick={() => pick(l.code)}
              className={`w-full flex items-center justify-between gap-3 px-3 py-2 text-sm text-left transition-colors hover:bg-white/[0.05] ${l.code === current.code ? "text-[#CCFF00]" : "text-zinc-300"}`}>
              <span className="flex items-center gap-2"><span className="text-base leading-none">{l.flag}</span> {l.label}</span>
              {l.code === current.code && <Check size={12} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
