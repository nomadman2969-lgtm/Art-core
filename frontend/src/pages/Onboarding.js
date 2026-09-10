import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Loader2, Palette, Upload, Rocket, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { KeepMoreStrip } from "../components/KeepMoreStrip";
import { useTranslation } from "react-i18next";

const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#CCFF00]";
const STEPS = [["onboarding.pick_theme", Palette], ["onboarding.upload_first", Upload], ["onboarding.publish", Rocket]];

export default function Onboarding() {
  const { t } = useTranslation();
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [themes, setThemes] = useState([]);
  const [theme, setTheme] = useState(null);
  const [busy, setBusy] = useState(false);
  const [art, setArt] = useState({ title: "", medium: "Acrylic", price: "", width_in: "", height_in: "", image: null });
  const [created, setCreated] = useState(null);
  const [settings, setSettings] = useState(null);

  useEffect(() => {
    api.get("/studio/themes").then((r) => setThemes(r.data));
    api.get("/studio/me").then((r) => setTheme(r.data.theme)).catch(() => {});
    api.get("/settings").then((r) => setSettings(r.data)).catch(() => {});
  }, []);

  const saveTheme = async () => {
    if (!theme) return toast.error("Pick a theme");
    setBusy(true);
    try { await api.patch("/studio", { theme }); setStep(1); } catch { toast.error("Couldn't save theme"); }
    setBusy(false);
  };

  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    setBusy(true);
    try {
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setArt((a) => ({ ...a, image: r.data.path }));
    } catch { toast.error("Upload failed"); }
    setBusy(false);
  };

  const saveArt = async (e) => {
    e.preventDefault();
    if (!art.image) return toast.error("Add an image of the piece");
    setBusy(true);
    try {
      const r = await api.post("/artworks", {
        title: art.title, medium: art.medium, price: Number(art.price), width_in: Number(art.width_in) || 12,
        height_in: Number(art.height_in) || 12, images: [art.image], description: "", kind: "original", quantity: 1, tags: [],
      });
      setCreated(r.data);
      setStep(2);
    } catch (er) { toast.error(er?.response?.data?.detail || "Couldn't save artwork"); }
    setBusy(false);
  };

  const publish = async () => {
    setBusy(true);
    try {
      await api.post("/studio/publish").catch(() => {});
      await api.post("/onboarding/complete");
      await refresh?.();
      const fee = settings?.upload_fee ?? 0;
      if (created && fee > 0) {
        const p = await api.post("/payments/upload-fee", { artwork_id: created.id, origin_url: ORIGIN });
        window.location.href = p.data.checkout_url;
        return;
      }
      toast.success("Your studio is live");
      nav(`/artist/${user.id}`);
    } catch { toast.error("Something went wrong"); }
    setBusy(false);
  };

  const skip = async () => { await api.post("/onboarding/complete").catch(() => {}); await refresh?.(); nav("/studio"); };

  return (
    <div data-testid="onboarding" className="max-w-4xl mx-auto px-4 md:px-8 pt-10 md:pt-16 pb-32">
      <div className="label-caps text-[#CCFF00] mb-3">{t("onboarding.welcome", { name: user?.name?.split(" ")[0] })}</div>
      <h1 className="font-anton text-4xl sm:text-5xl lg:text-6xl uppercase leading-[0.9]">{t("onboarding.title_1")}<br />{t("onboarding.title_2")}</h1>
      <div className="flex gap-2 mt-8 mb-10">
        {STEPS.map(([label, Icon], i) => (
          <div key={label} data-testid={`onboarding-step-${i}`} className={`flex-1 border-t-2 pt-3 ${i <= step ? "border-[#CCFF00]" : "border-white/10"}`}>
            <div className={`flex items-center gap-2 text-xs ${i <= step ? "text-white" : "text-zinc-600"}`}>
              {i < step ? <Check size={12} className="text-[#CCFF00]" /> : <Icon size={12} />} <span className="hidden sm:inline">{t(label)}</span><span className="sm:hidden">{t("onboarding.step", { n: i + 1 })}</span>
            </div>
          </div>
        ))}
      </div>

      {step === 0 && <div className="mb-10"><KeepMoreStrip compact cta={false} /></div>}

      {step === 0 && (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {themes.map((t) => (
              <button key={t.id} data-testid={`theme-${t.id}`} onClick={() => setTheme(t.id)}
                className={`text-left rounded-sm overflow-hidden border transition-colors ${theme === t.id ? "border-[#CCFF00]" : "border-white/10 hover:border-white/30"}`}>
                <div className="h-24 bg-cover bg-center" style={{ backgroundImage: `url(${t.bg_url})` }} />
                <div className="p-3">
                  <div className="font-unbounded text-xs font-semibold flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: t.accent }} />{t.name}</div>
                  <div className="text-[11px] text-zinc-500 mt-1 line-clamp-1">{t.vibe}</div>
                </div>
              </button>
            ))}
          </div>
          <div className="flex justify-between items-center mt-8">
            <button data-testid="onboarding-skip" onClick={skip} className="label-caps text-zinc-500 hover:text-white">Skip for now</button>
            <button data-testid="onboarding-next-0" onClick={saveTheme} disabled={busy || !theme} className="btn-lime flex items-center gap-2">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />} Continue
            </button>
          </div>
        </div>
      )}

      {step === 1 && (
        <form onSubmit={saveArt} className="grid md:grid-cols-2 gap-6">
          <label data-testid="onboarding-dropzone" className="border border-dashed border-white/15 rounded-sm min-h-[260px] flex items-center justify-center cursor-pointer bg-cover bg-center hover:border-[#CCFF00]/50"
            style={{ backgroundImage: art.image ? `url(${fileUrl(art.image)})` : undefined }}>
            {!art.image && <div className="text-center text-zinc-500 text-sm"><Upload size={22} className="mx-auto mb-2" />{busy ? "Uploading…" : "Tap to upload a photo of your work"}</div>}
            <input data-testid="onboarding-file" type="file" accept="image/*" className="hidden" onChange={upload} />
          </label>
          <div className="space-y-3">
            <input data-testid="onboarding-title" required value={art.title} onChange={(e) => setArt({ ...art, title: e.target.value })} placeholder="Title" className={inputCls} />
            <div className="grid grid-cols-2 gap-3">
              <select data-testid="onboarding-medium" value={art.medium} onChange={(e) => setArt({ ...art, medium: e.target.value })} className={inputCls}>
                {["Oil", "Acrylic", "Watercolor", "Mixed Media", "Digital", "Photography", "Sculpture", "Print"].map((m) => <option key={m}>{m}</option>)}
              </select>
              <input data-testid="onboarding-price" required type="number" min="1" step="1" value={art.price} onChange={(e) => setArt({ ...art, price: e.target.value })} placeholder="Price (USD)" className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <input data-testid="onboarding-width" type="number" step="0.5" value={art.width_in} onChange={(e) => setArt({ ...art, width_in: e.target.value })} placeholder="Width (in)" className={inputCls} />
              <input data-testid="onboarding-height" type="number" step="0.5" value={art.height_in} onChange={(e) => setArt({ ...art, height_in: e.target.value })} placeholder="Height (in)" className={inputCls} />
            </div>
            <div className="flex justify-between items-center pt-2">
              <button type="button" data-testid="onboarding-skip-art" onClick={() => setStep(2)} className="label-caps text-zinc-500 hover:text-white">{t("onboarding.upload_later")}</button>
              <button data-testid="onboarding-next-1" type="submit" disabled={busy} className="btn-lime flex items-center gap-2">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />} Continue
              </button>
            </div>
          </div>
        </form>
      )}

      {step === 2 && (
        <div className="glass-card p-8 rounded-sm">
          <div className="font-anton text-3xl uppercase">Ready to go live</div>
          <ul className="mt-4 space-y-2 text-sm text-zinc-300">
            <li className="flex items-center gap-2"><Check size={14} className="text-[#CCFF00]" /> Theme: <span className="text-white">{themes.find((t) => t.id === theme)?.name || "Default"}</span></li>
            <li className="flex items-center gap-2"><Check size={14} className={created ? "text-[#CCFF00]" : "text-zinc-600"} /> First piece: <span className="text-white">{created?.title || "none yet"}</span></li>
            <li className="flex items-center gap-2"><Check size={14} className="text-[#CCFF00]" /> Studio page: <span className="text-white">/artist/{user?.id?.slice(0, 8)}…</span></li>
          </ul>
          {created && (settings?.upload_fee ?? 0) > 0 && <div className="text-xs text-zinc-500 mt-4">A ${settings.upload_fee} listing fee is charged to make your first piece purchasable — you'll be taken to checkout.</div>}
          <button data-testid="onboarding-publish" onClick={publish} disabled={busy} className="btn-lime mt-6 w-full !py-3 flex items-center justify-center gap-2">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />} Publish my studio
          </button>
        </div>
      )}
    </div>
  );
}
