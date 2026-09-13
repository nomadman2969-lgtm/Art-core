import React from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FoundingBanner } from "./FoundingWaiver";

const ROWS = [
  { name: "Art Core", keep: 93, accent: "#CCFF00", note: "4% fee + card processing. No listing fees, no subscription." },
  { name: "Etsy", keep: 88, note: "6.5% + 3% processing + listing fees + offsite ads" },
  { name: "Chairish", keep: 75, note: "20–30% commission on furniture & decor" },
  { name: "Saatchi Art", keep: 65, note: "35–40% commission" },
  { name: "Singulart", keep: 50, note: "~50% commission" },
];

export function KeepMoreStrip({ compact = false, cta = true }) {
  const { t } = useTranslation();
  return (
    <section className={`${compact ? "" : "max-w-[1600px] mx-auto px-6 md:px-12 py-24"}`} data-testid="keep-more-strip">
      <div className="mb-6"><FoundingBanner compact={compact} /></div>
      <div className="glass-card rounded-sm p-8 md:p-14 relative overflow-hidden">
        <div className="absolute -top-32 -left-32 w-80 h-80 bg-[#CCFF00] rounded-full opacity-[0.07] blur-3xl" />
        <div className="relative grid lg:grid-cols-[1fr_1.3fr] gap-10 items-start">
          <div>
            <div className="label-caps text-[#CCFF00]">{t("keep.kicker")}</div>
            <h2 className={`font-anton uppercase mt-4 leading-[0.9] ${compact ? "text-3xl md:text-5xl" : "text-4xl sm:text-5xl lg:text-6xl"}`}>
              {t("keep.title_1")} <span className="text-[#CCFF00]">~93%</span><br />{t("keep.title_2")}
            </h2>
            <p className="text-zinc-400 mt-6 max-w-md text-sm md:text-base">
              {t("keep.body")}
            </p>
            {cta && (
              <div className="flex flex-wrap gap-4 mt-8">
                <Link to="/register?role=artist" data-testid="keep-more-cta" className="btn-lime">{t("keep.cta")}</Link>
              </div>
            )}
          </div>
          <div className="space-y-3" data-testid="keep-more-table">
            {ROWS.map((r) => (
              <div key={r.name} className="group">
                <div className="flex items-baseline justify-between gap-3 text-xs">
                  <span className={`label-caps ${r.accent ? "text-white" : "text-zinc-400"}`}>{r.name}</span>
                  <span className={`font-unbounded text-sm ${r.accent ? "text-[#CCFF00]" : "text-zinc-300"}`}>{r.keep}%</span>
                </div>
                <div className="h-2 mt-1.5 bg-white/[0.05] rounded-sm overflow-hidden">
                  <div className="h-full rounded-sm transition-[width] duration-700" style={{ width: `${r.keep}%`, background: r.accent || "rgba(255,255,255,0.28)" }} />
                </div>
                <div className="text-[10px] text-zinc-600 mt-1">{r.note}</div>
              </div>
            ))}
            <div className="text-[10px] text-zinc-600 pt-2">{t("keep.footnote")}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
