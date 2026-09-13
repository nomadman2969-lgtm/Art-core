import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { AnalyticsPanel } from "../components/studio/AnalyticsPanel";
import { WaiverBadge } from "../components/FoundingWaiver";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Plus, Gavel, Sparkles, Eye, Palette as PaletteIcon } from "lucide-react";
import {
  SectionH, Stat, BackgroundEditor, TemplatesPicker,
  SectionsEditor, FeaturedEditor, StoryEditor, PostsEditor,
  PayoutsPanel, ArtworkRow, CommissionRequestsPanel,
} from "../components/studio/StudioParts";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function StudioEditor() {
  const { t } = useTranslation();
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("overview");
  const [dashboard, setDashboard] = useState(null);
  const [artworks, setArtworks] = useState([]);
  const [config, setConfig] = useState(null);
  const [themes, setThemes] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [publishBusy, setPublishBusy] = useState(false);

  const loadAll = async () => {
    api.get("/artist/dashboard").then((r) => setDashboard(r.data));
    api.get("/artworks/mine").then((r) => setArtworks(r.data));
    api.get(`/studio/${user.id}`).then((r) => setConfig(r.data.config));
    api.get("/studio/themes").then((r) => setThemes(r.data));
    api.get("/studio/analytics/me").then((r) => setAnalytics(r.data));
  };
  useEffect(() => { if (user) loadAll(); }, [user]);

  // Merged live view of "current draft" — draft over published
  const draftView = React.useMemo(() => {
    if (!config) return null;
    return { ...config, ...(config.draft || {}) };
  }, [config]);

  const saveConfig = async (patch) => {
    setDirty(true);
    try {
      const r = await api.patch("/studio", patch);
      setConfig(r.data);
      setDirty(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); setDirty(false); }
  };

  const publish = async () => {
    setPublishBusy(true);
    try {
      const r = await api.post("/studio/publish");
      setConfig(r.data);
      toast.success("Studio published");
    } catch (e) { toast.error(e?.response?.data?.detail || "Publish failed"); }
    setPublishBusy(false);
  };

  const discard = async () => {
    if (!confirm("Discard all unpublished changes?")) return;
    setPublishBusy(true);
    try {
      const r = await api.post("/studio/discard-draft");
      setConfig(r.data);
      toast.success("Draft discarded");
    } catch (e) { toast.error("Failed"); }
    setPublishBusy(false);
  };

  const runAI = async () => {
    if (!aiPrompt.trim()) return;
    setAiBusy(true);
    try {
      const r = await api.post("/studio/ai-design", { prompt: aiPrompt });
      const c = r.data.config;
      const nextSections = (draftView?.sections || []).map((s) => ({
        ...s, title: c.section_titles?.[s.kind] || s.title,
      }));
      await saveConfig({
        theme: c.theme, accent_color: c.accent_color, lighting: c.lighting,
        typography: c.typography, sections: nextSections,
      });
      toast.success("Draft redesigned — review then Publish");
    } catch (er) { toast.error(er?.response?.data?.detail || "AI failed"); }
    setAiBusy(false);
  };

  const payFee = async (id) => {
    try {
      const r = await api.post("/payments/upload-fee", { artwork_id: id, origin_url: ORIGIN });
      if (r.data.free) { toast.success("Live!"); loadAll(); return; }
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const submitAotw = async (id) => {
    try { await api.post(`/artworks/${id}/submit-aotw`); toast.success("Submitted"); loadAll(); }
    catch { toast.error("Only live artworks can be submitted"); }
  };

  if (!user || !config || !dashboard) return <div className="py-32 text-center label-caps text-zinc-500">Loading Studio...</div>;
  const hasDraft = !!config.draft;

  const tabs = [
    ["overview", t("studio.overview")],
    ["theme", t("studio.theme")],
    ["sections", t("studio.sections")],
    ["story", t("studio.story")],
    ["posts", t("studio.posts")],
    ["artworks", t("studio.artworks")],
    ["featured", t("studio.featured")],
    ["requests", t("studio.requests")],
    ["analytics", t("studio.analytics")],
    ["payouts", t("studio.payouts")],
  ];

  return (
    <div data-testid="studio-editor" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-14 pb-32">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="label-caps text-[#CCFF00]"><PaletteIcon size={12} className="inline mr-2" /> {t("studio.kicker")}</div>
          <h1 className="font-anton text-5xl md:text-7xl uppercase mt-3">{t("studio.hey", { name: user.name })}</h1>
          <div className="text-zinc-500 text-sm mt-2">
            {hasDraft ? <span className="text-[#F5A623]">You have unpublished changes.</span> : "Visitors see the published version."}
            {dirty && <span className="text-[#F5A623] ml-2">saving...</span>}
          </div>
        </div>
        <div className="flex gap-3 flex-wrap">
          <Link to={`/artist/${user.id}?preview=1`} data-testid="preview-studio" className="btn-ghost"><Eye size={14} className="mr-2" /> Preview</Link>
          {hasDraft && (
            <>
              <button data-testid="publish-studio" onClick={publish} disabled={publishBusy} className="btn-lime">
                {publishBusy ? "Publishing..." : "Publish Changes"}
              </button>
              <button data-testid="discard-draft" onClick={discard} disabled={publishBusy} className="btn-ghost">Discard</button>
            </>
          )}
          {!hasDraft && (
            <Link to={`/artist/${user.id}`} data-testid="view-studio" className="btn-ghost">View Live</Link>
          )}
          <Link to="/auctions/new" className="btn-violet"><Gavel size={14} className="mr-2" /> Launch Auction</Link>
          <Link to="/studio/upload" data-testid="new-artwork-btn" className="btn-lime"><Plus size={14} className="mr-2" /> New Artwork</Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mb-10 border-b border-white/8 overflow-x-auto">
        {tabs.map(([k, l]) => (
          <button key={k} data-testid={`tab-${k}`} onClick={() => setTab(k)}
            className={`label-caps text-xs px-4 py-3 border-b-2 whitespace-nowrap ${tab === k ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}>{l}</button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <div className="mb-6"><WaiverBadge /></div>
          <div className="grid md:grid-cols-4 gap-4 mb-12">
            <Stat label={t("studio.live_listings")} value={dashboard.listings.live} accent="#FFFFFF" />
            <Stat label={t("studio.sold")} value={dashboard.listings.sold} accent="#CCFF00" />
            <Stat label={t("studio.pending_fee")} value={dashboard.listings.pending_fee} accent="#FF4D4D" />
            <Stat label={t("studio.net_earnings")} value={`$${dashboard.total_net.toLocaleString()}`} accent="#7C3AED" />
          </div>
          <SectionH title="Quick Start Templates">
            <TemplatesPicker save={saveConfig} />
          </SectionH>
          <div className="mt-8" />
          <SectionH title="Studio Design AI">
            <div className="glass-card p-6 rounded-sm">
              <div className="label-caps mb-3 text-[#CCFF00]"><Sparkles size={12} className="inline mr-2" /> Describe your studio</div>
              <div className="flex gap-2">
                <input data-testid="ai-prompt" value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="e.g. Dark underground graffiti gallery with neon lime"
                  className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none focus:border-[#CCFF00]" />
                <button data-testid="ai-run" disabled={aiBusy || !aiPrompt.trim()} onClick={runAI} className="btn-lime">
                  {aiBusy ? "Designing..." : "Redesign"}
                </button>
              </div>
              <div className="text-xs text-zinc-500 mt-3">Powered by Claude · Instantly restyles your theme, accent, lighting, and section titles.</div>
            </div>
          </SectionH>
          <div className="mt-10 grid md:grid-cols-2 gap-4">
            <Link to={`/artist/${user.id}?preview=1`} className="glass-card p-8 rounded-sm hover-lift-card block">
              <div className="label-caps text-[#CCFF00]">{t("studio.preview")}</div>
              <div className="font-anton text-3xl mt-2">See your studio →</div>
            </Link>
            <button onClick={() => setTab("theme")} className="glass-card p-8 rounded-sm hover-lift-card text-left">
              <div className="label-caps text-[#7C3AED]">Design</div>
              <div className="font-anton text-3xl mt-2">Change theme →</div>
            </button>
          </div>
        </>
      )}

      {tab === "theme" && (
        <div className="space-y-10">
          <SectionH title="Theme">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {themes.map((t) => (
                <button key={t.id} data-testid={`theme-${t.id}`} onClick={() => saveConfig({ theme: t.id })}
                  className={`relative aspect-[4/3] overflow-hidden border rounded-sm text-left ${draftView.theme === t.id ? "border-[#CCFF00]" : "border-white/10"} hover:border-[#CCFF00] transition-colors`}>
                  {t.bg_url ? <img src={t.bg_url} className="absolute inset-0 w-full h-full object-cover opacity-60" alt="" /> : <div className="absolute inset-0 bg-gradient-to-br from-[#0A0A0C] to-[#1A1A1E]" />}
                  <div className="absolute inset-0 bg-gradient-to-t from-black to-transparent" />
                  <div className="relative h-full flex flex-col justify-end p-4">
                    <div className="font-anton text-xl uppercase">{t.name}</div>
                    <div className="w-6 h-1 mt-1" style={{ background: t.accent }} />
                    {draftView.theme === t.id && <div className="badge-lime absolute top-2 right-2">Active</div>}
                  </div>
                </button>
              ))}
            </div>
          </SectionH>

          <SectionH title="Background">
            <BackgroundEditor config={draftView} save={saveConfig} />
          </SectionH>

          <SectionH title="Accent Color">
            <div className="flex flex-wrap gap-3 items-center">
              {["#CCFF00", "#7C3AED", "#FF4D4D", "#00E5FF", "#F5A623", "#FF6EC7", "#D4AF37", "#FFFFFF"].map((c) => (
                <button key={c} data-testid={`accent-${c}`} onClick={() => saveConfig({ accent_color: c })}
                  className={`w-10 h-10 rounded-sm border-2 ${draftView.accent_color === c ? "border-white" : "border-white/20"}`}
                  style={{ background: c }} />
              ))}
              <input type="color" data-testid="accent-picker" value={draftView.accent_color || "#CCFF00"}
                onChange={(e) => saveConfig({ accent_color: e.target.value })}
                className="w-10 h-10 rounded-sm bg-transparent border border-white/20 cursor-pointer" />
            </div>
          </SectionH>

          <SectionH title="Lighting">
            <div className="grid md:grid-cols-3 gap-3">
              {["gallery", "spotlight", "neon", "warm", "cool", "ambient"].map((p) => (
                <button key={p} data-testid={`lighting-${p}`}
                  onClick={() => saveConfig({ lighting: { ...draftView.lighting, preset: p } })}
                  className={`p-4 border rounded-sm text-left ${draftView.lighting?.preset === p ? "border-[#CCFF00]" : "border-white/10 hover:border-white/30"}`}>
                  <div className="font-unbounded uppercase text-sm">{p}</div>
                </button>
              ))}
            </div>
            <div className="mt-4">
              <div className="label-caps mb-2">Intensity ({draftView.lighting?.intensity ?? 70}%)</div>
              <input data-testid="lighting-intensity" type="range" min="20" max="100" value={draftView.lighting?.intensity ?? 70}
                onChange={(e) => saveConfig({ lighting: { ...draftView.lighting, intensity: Number(e.target.value) } })}
                className="w-full accent-[#CCFF00]" />
            </div>
          </SectionH>

          <SectionH title="AI Designer">
            <div className="glass-card p-6 rounded-sm">
              <div className="label-caps mb-3 text-[#CCFF00]"><Sparkles size={12} className="inline mr-2" /> Describe the vibe</div>
              <div className="flex gap-2">
                <input data-testid="ai-prompt-theme" value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="Cyberpunk digital gallery with cyan neon and glitchy titles..."
                  className="flex-1 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none focus:border-[#CCFF00]" />
                <button disabled={aiBusy || !aiPrompt.trim()} onClick={runAI} className="btn-lime">
                  {aiBusy ? "Designing..." : "Redesign"}
                </button>
              </div>
            </div>
          </SectionH>
        </div>
      )}

      {tab === "sections" && <SectionsEditor config={draftView} save={saveConfig} />}
      {tab === "story" && <StoryEditor config={draftView} save={saveConfig} user={user} refresh={refresh} />}
      {tab === "posts" && <PostsEditor userId={user.id} />}
      {tab === "featured" && <FeaturedEditor config={draftView} save={saveConfig} artworks={artworks} />}

      {tab === "artworks" && (
        <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
          {artworks.length === 0 ? (
            <div className="text-zinc-500 py-16 label-caps text-center">No artworks yet. <Link to="/studio/upload" className="text-[#CCFF00] ml-2">Upload →</Link></div>
          ) : artworks.map((a) => (
            <ArtworkRow key={a.id} a={a} onReload={loadAll} onPayFee={payFee} onSubmitAotw={submitAotw} />
          ))}
        </div>
      )}

      {tab === "analytics" && analytics && <AnalyticsPanel analytics={analytics} />}

      {tab === "payouts" && <PayoutsPanel dashboard={dashboard} refresh={loadAll} refreshUser={refresh} />}
      {tab === "requests" && <CommissionRequestsPanel />}
    </div>
  );
}
