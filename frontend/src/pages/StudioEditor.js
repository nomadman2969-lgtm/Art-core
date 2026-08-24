import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Plus, Gavel, Sparkles, Eye, Palette as PaletteIcon, GripVertical, Trash2, ExternalLink } from "lucide-react";
const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function StudioEditor() {
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
    ["overview", "Overview"],
    ["theme", "Theme & Look"],
    ["sections", "Sections"],
    ["story", "My Story"],
    ["posts", "Posts"],
    ["artworks", "Artworks"],
    ["featured", "Featured"],
    ["requests", "Requests"],
    ["analytics", "Analytics"],
    ["payouts", "Payouts"],
  ];

  return (
    <div data-testid="studio-editor" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-14 pb-32">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="label-caps text-[#CCFF00]"><PaletteIcon size={12} className="inline mr-2" /> Studio Editor</div>
          <h1 className="font-anton text-5xl md:text-7xl uppercase mt-3">Hey, {user.name}.</h1>
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

      {/* OVERVIEW */}
      {tab === "overview" && (
        <div className="grid md:grid-cols-4 gap-4 mb-12">
          <Stat label="Live listings" value={dashboard.listings.live} accent="#FFFFFF" />
          <Stat label="Sold" value={dashboard.listings.sold} accent="#CCFF00" />
          <Stat label="Pending fee" value={dashboard.listings.pending_fee} accent="#FF4D4D" />
          <Stat label="Net earnings" value={`$${dashboard.total_net.toLocaleString()}`} accent="#7C3AED" />
        </div>
      )}
      {tab === "overview" && (
        <>
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
            <Link to={`/artist/${user.id}`} className="glass-card p-8 rounded-sm hover-lift-card block">
              <div className="label-caps text-[#CCFF00]">Preview</div>
              <div className="font-anton text-3xl mt-2">See your live studio →</div>
            </Link>
            <button onClick={() => setTab("theme")} className="glass-card p-8 rounded-sm hover-lift-card text-left">
              <div className="label-caps text-[#7C3AED]">Design</div>
              <div className="font-anton text-3xl mt-2">Change theme →</div>
            </button>
          </div>
        </>
      )}

      {/* THEME */}
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

      {/* SECTIONS */}
      {tab === "sections" && (
        <SectionsEditor config={draftView} save={saveConfig} />
      )}

      {/* STORY */}
      {tab === "story" && (
        <StoryEditor config={draftView} save={saveConfig} user={user} refresh={refresh} />
      )}

      {/* POSTS */}
      {tab === "posts" && (
        <PostsEditor userId={user.id} />
      )}

      {/* FEATURED */}
      {tab === "featured" && (
        <FeaturedEditor config={draftView} save={saveConfig} artworks={artworks} />
      )}

      {/* ARTWORKS */}
      {tab === "artworks" && (
        <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
          {artworks.length === 0 ? (
            <div className="text-zinc-500 py-16 label-caps text-center">No artworks yet. <Link to="/studio/upload" className="text-[#CCFF00] ml-2">Upload →</Link></div>
          ) : artworks.map((a) => (
            <ArtworkRow key={a.id} a={a} onReload={loadAll} onPayFee={payFee} onSubmitAotw={submitAotw} />
          ))}
        </div>
      )}

      {/* ANALYTICS */}
      {tab === "analytics" && analytics && (
        <div className="space-y-8">
          <div className="grid md:grid-cols-3 lg:grid-cols-6 gap-4">
            <Stat label="Studio visits" value={analytics.visits} accent="#CCFF00" />
            <Stat label="Followers" value={analytics.followers} accent="#7C3AED" />
            <Stat label="Total likes" value={analytics.total_likes} accent="#FF4D4D" />
            <Stat label="Sales" value={analytics.sales} accent="#00E5FF" />
            <Stat label="Revenue" value={`$${analytics.revenue.toLocaleString()}`} accent="#F5A623" />
            <Stat label="Artworks" value={analytics.artworks_count} accent="#FFFFFF" />
          </div>
          <SectionH title="Top artworks by likes">
            {analytics.top_artworks.length === 0 ? (
              <div className="text-zinc-500 label-caps py-8 text-center">No liked artworks yet.</div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {analytics.top_artworks.map((a) => (
                  <Link key={a.id} to={`/artwork/${a.id}`} className="border border-white/8 rounded-sm hover-lift-card block">
                    <img src={resolveImg(a.images?.[0])} className="w-full aspect-square object-cover" alt="" />
                    <div className="p-3">
                      <div className="font-unbounded text-sm truncate">{a.title}</div>
                      <div className="label-caps mt-1 text-[#FF4D4D]">♥ {a.likes}</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </SectionH>
        </div>
      )}

      {/* PAYOUTS */}
      {tab === "payouts" && (
        <PayoutsPanel dashboard={dashboard} refresh={loadAll} refreshUser={refresh} />
      )}

      {tab === "requests" && (
        <CommissionRequestsPanel />
      )}
    </div>
  );
}

function SectionH({ title, children }) {
  return (
    <div>
      <div className="label-caps mb-4">{title}</div>
      {children}
    </div>
  );
}

function BackgroundEditor({ config, save }) {
  const [uploading, setUploading] = useState(false);
  const bg = config.background || { type: "theme", texture: "none", texture_opacity: 25 };
  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const url = `${api.defaults.baseURL}/files/${r.data.path}`;
      save({ background: { ...bg, type: "image", value: url } });
      toast.success("Background updated");
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };
  const setTexture = (texture) => save({ background: { ...bg, texture } });
  const setOpacity = (v) => save({ background: { ...bg, texture_opacity: Number(v) } });
  const setColor = (color) => save({ background: { ...bg, type: "color", value: color } });

  const TEXTURES = [
    { id: "none", label: "None" },
    { id: "graffiti", label: "Graffiti" },
    { id: "brick", label: "Brick" },
    { id: "concrete", label: "Concrete" },
    { id: "grid", label: "Neon Grid" },
    { id: "noise", label: "Grain" },
    { id: "paper", label: "Paper" },
  ];
  return (
    <div className="space-y-6">
      <div>
        <div className="label-caps mb-2">Base</div>
        <div className="flex flex-wrap gap-3 items-center">
          <button data-testid="bg-theme" onClick={() => save({ background: { ...bg, type: "theme", value: null } })}
            className={`px-4 py-3 border rounded-sm label-caps text-xs ${bg.type === "theme" ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-400 hover:border-white/30"}`}>Theme Default</button>
          <label className={`px-4 py-3 border rounded-sm label-caps text-xs cursor-pointer ${bg.type === "image" ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-400 hover:border-white/30"}`}>
            {uploading ? "Uploading..." : "Upload Image"}
            <input data-testid="bg-upload" type="file" accept="image/*" onChange={upload} className="hidden" />
          </label>
          <button data-testid="bg-color" onClick={() => setColor(bg.value?.startsWith("#") ? bg.value : "#0A0A0C")}
            className={`px-4 py-3 border rounded-sm label-caps text-xs ${bg.type === "color" ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-400 hover:border-white/30"}`}>Solid Color</button>
          {bg.type === "color" && (
            <input type="color" data-testid="bg-color-picker" value={bg.value || "#0A0A0C"} onChange={(e) => setColor(e.target.value)}
              className="w-10 h-10 rounded-sm bg-transparent border border-white/20 cursor-pointer" />
          )}
        </div>
        {bg.type === "image" && bg.value && (
          <div className="mt-3">
            <img src={bg.value} alt="" className="w-full max-w-lg aspect-[16/6] object-cover border border-white/10 rounded-sm" />
          </div>
        )}
      </div>

      <div>
        <div className="label-caps mb-2">Texture Overlay</div>
        <div className="flex flex-wrap gap-2">
          {TEXTURES.map((t) => (
            <button key={t.id} data-testid={`tex-${t.id}`} onClick={() => setTexture(t.id)}
              className={`px-3 py-2 border rounded-sm label-caps text-xs ${bg.texture === t.id ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-400 hover:border-white/30"}`}>
              {t.label}
            </button>
          ))}
        </div>
        {bg.texture && bg.texture !== "none" && (
          <div className="mt-3">
            <div className="label-caps mb-2">Intensity ({bg.texture_opacity ?? 25}%)</div>
            <input data-testid="tex-opacity" type="range" min="5" max="80" value={bg.texture_opacity ?? 25}
              onChange={(e) => setOpacity(e.target.value)} className="w-full accent-[#CCFF00]" />
          </div>
        )}
      </div>
    </div>
  );
}
function Stat({ label, value, accent }) {
  return (
    <div className="glass-card p-5 rounded-sm">
      <div className="label-caps">{label}</div>
      <div className="font-anton text-4xl mt-3" style={{ color: accent }}>{value}</div>
    </div>
  );
}

// ---------- Sections editor ----------
const SECTION_KINDS = [
  { kind: "featured_works", label: "Featured Works", gallery: true },
  { kind: "available_now", label: "Available Now", gallery: true },
  { kind: "sold_works", label: "Sold Works", gallery: true },
  { kind: "upcoming_auctions", label: "Live Auctions" },
  { kind: "feed", label: "Studio Feed" },
  { kind: "story", label: "My Story" },
  { kind: "commission", label: "Commission Me" },
  { kind: "announcement", label: "Announcement" },
  { kind: "text_block", label: "Text Block" },
  { kind: "button_cta", label: "Button / CTA" },
  { kind: "image_block", label: "Image Block" },
  { kind: "custom", label: "Custom" },
];

const LAYOUT_OPTIONS = [
  { id: "grid", label: "Grid" },
  { id: "masonry", label: "Masonry" },
  { id: "salon", label: "Salon Wall" },
  { id: "showcase", label: "Single Showcase" },
  { id: "carousel", label: "Carousel" },
];

function SectionsEditor({ config, save }) {
  const sections = config.sections || [];
  const [expanded, setExpanded] = useState(null);
  const move = (i, dir) => {
    const arr = [...sections];
    const j = i + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    arr.forEach((s, idx) => (s.order = idx));
    save({ sections: arr });
  };
  const update = (id, patch) => {
    const arr = sections.map((s) => (s.id === id ? { ...s, ...patch } : s));
    save({ sections: arr });
  };
  const remove = (id) => save({ sections: sections.filter((s) => s.id !== id) });
  const add = (kind) => {
    const meta = SECTION_KINDS.find((k) => k.kind === kind);
    const s = {
      id: `s-${Date.now()}`, kind, title: meta?.label || "New Section",
      order: sections.length, visible: true,
    };
    if (meta?.gallery) s.layout = "grid";
    if (kind === "announcement") { s.body = "Big news for my collectors..."; s.variant = "info"; }
    if (kind === "text_block") s.body = "Write anything you'd like your visitors to know here.";
    if (kind === "button_cta") { s.body = "Interested in a commission?"; s.button_text = "Get in touch"; s.button_link = "#commission"; }
    if (kind === "image_block") { s.caption = "Add a caption"; s.body = ""; }
    save({ sections: [...sections, s] });
    setExpanded(s.id);
  };
  return (
    <div className="space-y-4">
      <div className="border border-white/8 rounded-sm divide-y divide-white/8">
        {sections.sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).map((s, i) => {
          const meta = SECTION_KINDS.find((k) => k.kind === s.kind);
          const isExpanded = expanded === s.id;
          const canExpand = ["custom", "text_block", "announcement", "button_cta", "image_block"].includes(s.kind) || meta?.gallery;
          return (
            <div key={s.id} data-testid={`section-row-${s.id}`}>
              <div className="p-4 flex flex-wrap items-center gap-3">
                <GripVertical size={14} className="text-zinc-500" />
                <div className="label-caps text-zinc-500 w-32 flex-shrink-0 truncate">{s.kind}</div>
                <input value={s.title} onChange={(e) => update(s.id, { title: e.target.value })}
                  className="flex-1 min-w-[180px] bg-transparent border-b border-white/10 focus:border-[#CCFF00] px-2 py-1 outline-none" />
                <label className="label-caps flex items-center gap-2">
                  <input type="checkbox" checked={s.visible !== false} onChange={(e) => update(s.id, { visible: e.target.checked })} /> Visible
                </label>
                <button onClick={() => move(i, -1)} className="label-caps hover:text-[#CCFF00]">↑</button>
                <button onClick={() => move(i, 1)} className="label-caps hover:text-[#CCFF00]">↓</button>
                {canExpand && (
                  <button data-testid={`toggle-${s.id}`} onClick={() => setExpanded(isExpanded ? null : s.id)} className="label-caps hover:text-[#CCFF00]">{isExpanded ? "Close" : "Edit"}</button>
                )}
                <button onClick={() => remove(s.id)} className="text-zinc-500 hover:text-[#FF4D4D]"><Trash2 size={14} /></button>
              </div>
              {isExpanded && canExpand && (
                <div className="px-4 pb-5 pt-1 bg-white/[0.02] space-y-3" data-testid={`section-editor-${s.id}`}>
                  {meta?.gallery && (
                    <div>
                      <div className="label-caps mb-2">Layout</div>
                      <div className="flex flex-wrap gap-2">
                        {LAYOUT_OPTIONS.map((l) => (
                          <button key={l.id} data-testid={`layout-${s.id}-${l.id}`} onClick={() => update(s.id, { layout: l.id })}
                            className={`px-3 py-2 border rounded-sm label-caps text-xs ${(s.layout || "grid") === l.id ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-400"}`}>{l.label}</button>
                        ))}
                      </div>
                    </div>
                  )}
                  {["announcement", "text_block", "custom"].includes(s.kind) && (
                    <div>
                      <div className="label-caps mb-2">Body</div>
                      <textarea data-testid={`body-${s.id}`} rows={s.kind === "announcement" ? 3 : 6}
                        value={s.body || ""} onChange={(e) => update(s.id, { body: e.target.value })}
                        placeholder="Write here..."
                        className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
                    </div>
                  )}
                  {s.kind === "announcement" && (
                    <div>
                      <div className="label-caps mb-2">Style</div>
                      <div className="flex gap-2">
                        {["info", "success", "warning"].map((v) => (
                          <button key={v} data-testid={`variant-${s.id}-${v}`} onClick={() => update(s.id, { variant: v })}
                            className={`px-3 py-2 border rounded-sm label-caps text-xs ${(s.variant || "info") === v ? "border-[#CCFF00] text-white" : "border-white/10 text-zinc-400"}`}>{v}</button>
                        ))}
                      </div>
                    </div>
                  )}
                  {s.kind === "button_cta" && (
                    <>
                      <div>
                        <div className="label-caps mb-2">Blurb</div>
                        <textarea rows={2} value={s.body || ""} onChange={(e) => update(s.id, { body: e.target.value })}
                          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
                      </div>
                      <div className="grid md:grid-cols-2 gap-3">
                        <label className="block">
                          <div className="label-caps mb-2">Button label</div>
                          <input data-testid={`btn-text-${s.id}`} value={s.button_text || ""} onChange={(e) => update(s.id, { button_text: e.target.value })}
                            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
                        </label>
                        <label className="block">
                          <div className="label-caps mb-2">Link (URL or #anchor)</div>
                          <input data-testid={`btn-link-${s.id}`} value={s.button_link || ""} onChange={(e) => update(s.id, { button_link: e.target.value })}
                            placeholder="https://... or #commission"
                            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
                        </label>
                      </div>
                    </>
                  )}
                  {s.kind === "image_block" && (
                    <ImageBlockEditor s={s} update={update} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div>
        <div className="label-caps mb-3">Add a section</div>
        <div className="flex flex-wrap gap-2">
          {SECTION_KINDS.map((k) => (
            <button key={k.kind} data-testid={`add-section-${k.kind}`} onClick={() => add(k.kind)} className="btn-ghost !py-2 !text-xs">+ {k.label}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ImageBlockEditor({ s, update }) {
  const [uploading, setUploading] = useState(false);
  const upload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      update(s.id, { image: r.data.path });
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };
  return (
    <>
      <div>
        <div className="label-caps mb-2">Image</div>
        {s.image && <img src={resolveImg(s.image)} className="w-full max-w-md aspect-video object-cover rounded-sm border border-white/10 mb-2" alt="" />}
        <label className="btn-ghost !py-2 !text-xs cursor-pointer inline-flex">
          {uploading ? "Uploading..." : s.image ? "Replace Image" : "Upload Image"}
          <input data-testid={`img-upload-${s.id}`} type="file" accept="image/*" onChange={upload} className="hidden" />
        </label>
      </div>
      <div>
        <div className="label-caps mb-2">Caption</div>
        <input value={s.caption || ""} onChange={(e) => update(s.id, { caption: e.target.value })}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
      </div>
      <div>
        <div className="label-caps mb-2">Description (optional)</div>
        <textarea rows={3} value={s.body || ""} onChange={(e) => update(s.id, { body: e.target.value })}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
      </div>
    </>
  );
}

// ---------- Featured artwork picker ----------
function FeaturedEditor({ config, save, artworks }) {
  const picks = config.featured_artwork_ids || [];
  const toggle = (id) => {
    const next = picks.includes(id) ? picks.filter((p) => p !== id) : [...picks, id].slice(0, 12);
    save({ featured_artwork_ids: next });
  };
  const liveArts = artworks.filter((a) => a.status === "live" || a.status === "sold");
  return (
    <div data-testid="featured-editor">
      <div className="glass-card p-6 rounded-sm mb-6">
        <div className="label-caps text-[#CCFF00]">Featured Works</div>
        <div className="text-sm text-zinc-400 mt-2">Pick up to 12 pieces to spotlight in the Featured Works section (in the exact order you tap them). Leave empty to show the artworks you've flagged as Featured elsewhere.</div>
      </div>
      {picks.length > 0 && (
        <div className="mb-6">
          <div className="label-caps mb-3">Selected order</div>
          <div className="flex gap-2 flex-wrap">
            {picks.map((pid, i) => {
              const a = liveArts.find((x) => x.id === pid);
              if (!a) return null;
              return (
                <div key={pid} className="relative">
                  <img src={resolveImg(a.images?.[0])} className="w-20 h-20 object-cover rounded-sm border-2 border-[#CCFF00]" alt="" />
                  <div className="absolute -top-2 -left-2 w-6 h-6 rounded-full bg-[#CCFF00] text-black text-xs font-bold flex items-center justify-center">{i + 1}</div>
                  <button onClick={() => toggle(pid)} className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-[#FF4D4D] text-white text-xs flex items-center justify-center">×</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div className="label-caps mb-3">All artworks</div>
      <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-3">
        {liveArts.map((a) => {
          const isPicked = picks.includes(a.id);
          return (
            <button key={a.id} data-testid={`feat-toggle-${a.id}`} onClick={() => toggle(a.id)}
              className={`relative aspect-square rounded-sm overflow-hidden border-2 transition-all ${isPicked ? "border-[#CCFF00] scale-95" : "border-white/10 hover:border-white/30"}`}>
              <img src={resolveImg(a.images?.[0])} className="w-full h-full object-cover" alt="" />
              {isPicked && <div className="absolute inset-0 bg-[#CCFF00]/20" />}
              <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1 truncate">
                <div className="text-xs font-unbounded truncate">{a.title}</div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------- Story editor ----------
function StoryEditor({ config, save, user, refresh }) {
  const [story, setStory] = useState(config.artist_story || {});
  const [bio, setBio] = useState(user.bio || "");
  const patch = (k, v) => setStory({ ...story, [k]: v });
  const saveAll = async () => {
    await save({ artist_story: story });
    await api.patch("/auth/me", { bio });
    await refresh();
    toast.success("Story saved");
  };
  const F = ({ label, field, ...rest }) => (
    <label className="block">
      <div className="label-caps mb-2">{label}</div>
      <input value={story[field] || ""} onChange={(e) => patch(field, e.target.value)}
        className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]" {...rest} />
    </label>
  );
  return (
    <div className="space-y-5 max-w-3xl">
      <label className="block">
        <div className="label-caps mb-2">Bio (shown at top of your Studio)</div>
        <textarea data-testid="bio-input" value={bio} onChange={(e) => setBio(e.target.value)} rows={4}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
      </label>
      <div className="grid md:grid-cols-2 gap-4">
        <F label="Location" field="location" />
        <F label="Style" field="style" placeholder="Abstract, street, mixed media..." />
        <F label="Active since (year)" field="years_active" />
        <F label="Education" field="education" />
        <F label="Exhibitions" field="exhibitions" />
        <F label="Awards" field="awards" />
      </div>
      <label className="block">
        <div className="label-caps mb-2">Influences / Inspiration</div>
        <textarea value={story.influences || ""} onChange={(e) => patch("influences", e.target.value)} rows={3}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
      </label>
      <div className="grid md:grid-cols-3 gap-4">
        <F label="Website" field="website" placeholder="https://" />
        <F label="Instagram" field="instagram" placeholder="@handle" />
        <F label="Twitter / X" field="twitter" placeholder="@handle" />
      </div>
      <button data-testid="save-story" onClick={saveAll} className="btn-lime mt-4">Save Story</button>
    </div>
  );
}

// ---------- Posts editor ----------
function PostsEditor({ userId }) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState("update");
  const [image, setImage] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [posts, setPosts] = useState([]);
  const load = () => api.get(`/posts?artist_id=${userId}`).then((r) => setPosts(r.data));
  useEffect(load, []);

  const uploadImage = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImage(r.data.path);
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };
  const post = async () => {
    if (!text.trim()) return;
    try {
      await api.post("/posts", { text, kind, image });
      setText(""); setImage(null); toast.success("Posted"); load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };
  const del = async (id) => {
    if (!confirm("Delete?")) return;
    await api.delete(`/posts/${id}`); load();
  };
  const pin = async (p) => { await api.patch(`/posts/${p.id}/pin`, { pinned: !p.pinned }); load(); };
  return (
    <div className="max-w-3xl space-y-8">
      <div className="glass-card p-6 rounded-sm">
        <div className="grid grid-cols-2 gap-3 mb-3">
          <select data-testid="post-kind" value={kind} onChange={(e) => setKind(e.target.value)} className="bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2">
            <option value="update">Update</option>
            <option value="wip">Work in progress</option>
            <option value="studio_photo">Studio photo</option>
            <option value="announcement">Announcement</option>
            <option value="auction">Auction</option>
            <option value="sold">Sold</option>
          </select>
          <div><input type="file" accept="image/*" onChange={uploadImage} className="text-xs" /></div>
        </div>
        <textarea data-testid="post-text" value={text} onChange={(e) => setText(e.target.value)} rows={4}
          placeholder="What's happening in the studio?" className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
        {image && <img src={fileUrl(image)} className="mt-3 w-40 rounded-sm" alt="" />}
        {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
        <button data-testid="post-create" onClick={post} className="btn-lime mt-4">Publish</button>
      </div>
      <div className="space-y-3">
        {posts.map((p) => (
          <div key={p.id} className="border border-white/8 rounded-sm p-4">
            <div className="flex justify-between items-center mb-2">
              <div className="label-caps">{p.pinned && "📌 "}{p.kind} · {new Date(p.created_at).toLocaleDateString()}</div>
              <div className="flex gap-2">
                <button onClick={() => pin(p)} className="label-caps hover:text-[#CCFF00]">{p.pinned ? "Unpin" : "Pin"}</button>
                <button onClick={() => del(p.id)} className="label-caps hover:text-[#FF4D4D]">Delete</button>
              </div>
            </div>
            <div className="text-zinc-200 whitespace-pre-wrap">{p.text}</div>
            {p.image && <img src={resolveImg(p.image)} className="mt-3 w-64 rounded-sm" alt="" />}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Payouts panel ----------
function PayoutsPanel({ dashboard, refresh, refreshUser }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const loadStatus = async () => {
    try {
      const r = await api.get("/connect/status");
      setStatus(r.data);
    } catch {}
  };
  React.useEffect(() => { loadStatus(); }, []);

  const startConnect = async () => {
    setBusy(true);
    try {
      const returnUrl = `${window.location.origin}/studio?connect=ok`;
      const r = await api.post("/connect/onboarding-link", { return_url: returnUrl, refresh_url: returnUrl });
      window.location.href = r.data.url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Connect onboarding unavailable");
      setBusy(false);
    }
  };
  const openDashboard = async () => {
    try {
      const r = await api.post("/connect/dashboard-link");
      window.open(r.data.url, "_blank");
    } catch (e) { toast.error(e?.response?.data?.detail || "Cannot open dashboard"); }
  };

  const chargesOn = status?.charges_enabled;
  const payoutsOn = status?.payouts_enabled;
  const requirements = status?.requirements_due || [];

  return (
    <div className="space-y-8 max-w-3xl">
      <div className="glass-card p-8 rounded-sm" data-testid="connect-panel">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="label-caps text-[#CCFF00]">Stripe Connect · Artist Payouts</div>
            <div className="mt-3">
              {!status ? <span className="text-zinc-500 label-caps">Loading...</span> :
               !status.connected ? <span className="text-[#F5A623] font-unbounded">Not connected</span> :
               chargesOn && payoutsOn ? <span className="text-[#CCFF00] font-unbounded">✓ Active — payouts flow direct to your bank</span> :
               <span className="text-[#F5A623] font-unbounded">Onboarding in progress</span>}
            </div>
            {requirements.length > 0 && (
              <div className="text-xs text-[#F5A623] mt-2">Stripe still needs: {requirements.slice(0, 4).join(", ")}{requirements.length > 4 ? "..." : ""}</div>
            )}
            <div className="text-xs text-zinc-500 mt-3 max-w-lg">
              Art Core uses Stripe Connect Express to route your share of each sale directly to your bank. The platform keeps its commission automatically; you receive the rest.
            </div>
          </div>
          <div className="flex flex-col gap-2">
            {(!status?.connected || !chargesOn) && (
              <button data-testid="connect-start" onClick={startConnect} disabled={busy} className="btn-lime">
                {busy ? "Opening..." : status?.connected ? "Continue Onboarding" : "Connect Stripe"}
              </button>
            )}
            {status?.connected && (
              <button data-testid="connect-dashboard" onClick={openDashboard} className="btn-ghost">Open Stripe Dashboard</button>
            )}
          </div>
        </div>
      </div>

      <div>
        <div className="label-caps mb-3">Recent Payouts</div>
        {dashboard.payouts.length === 0 ? <div className="text-zinc-500 label-caps">No payouts yet.</div> : (
          <div className="border border-white/8 divide-y divide-white/8 text-sm rounded-sm">
            {dashboard.payouts.slice(0, 10).map((p, i) => (
              <div key={i} className="p-4 flex justify-between items-center flex-wrap gap-3">
                <div className="text-zinc-400 label-caps">{new Date(p.created_at).toLocaleDateString()}</div>
                <div className="font-anton text-xl">${p.net.toFixed(2)} <span className="text-zinc-500 text-xs font-manrope">of ${p.gross.toFixed(2)}</span></div>
                <div className="label-caps" style={{ color:
                  p.status === "auto_transferred" ? "#CCFF00" :
                  p.status === "transferred" ? "#CCFF00" :
                  p.status === "released" ? "#F5A623" :
                  "#71717A"
                }}>{
                  p.status === "auto_transferred" ? "Instant Payout" :
                  p.status === "transferred" ? "Transferred" :
                  p.status === "released" ? "Released (Manual)" :
                  p.status
                }</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ArtworkRow({ a, onReload, onPayFee, onSubmitAotw }) {
  const del = async () => {
    if (!confirm(`Delete "${a.title}"?`)) return;
    try { await api.delete(`/artworks/${a.id}`); toast.success("Deleted"); onReload(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const markSold = async () => {
    if (!confirm(`Mark "${a.title}" as sold?`)) return;
    try { await api.post(`/artworks/${a.id}/mark-sold`); toast.success("Marked sold"); onReload(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  return (
    <div data-testid={`my-art-${a.id}`} className="p-4 flex flex-wrap items-center gap-4">
      <img src={resolveImg(a.images?.[0])} className="w-16 h-16 object-cover rounded-sm" alt="" />
      <div className="flex-1 min-w-[200px]">
        <div className="font-unbounded text-lg font-semibold">{a.title}</div>
        <div className="label-caps mt-1">${Number(a.price).toLocaleString()} · <span className={
          a.status === "live" ? "text-[#CCFF00]" : a.status === "sold" ? "text-[#7C3AED]" : "text-[#FF4D4D]"
        }>{a.status}</span>{a.kind && a.kind !== "original" ? ` · ${a.kind}` : ""}</div>
      </div>
      {a.status === "pending_fee" && <button data-testid={`pay-fee-${a.id}`} onClick={() => onPayFee(a.id)} className="btn-lime !py-2 !text-xs">Pay Fee</button>}
      {a.status === "live" && !a.aotw_submitted && <button onClick={() => onSubmitAotw(a.id)} className="btn-ghost !py-2 !text-xs">Feature</button>}
      {a.status === "live" && <button data-testid={`mark-sold-${a.id}`} onClick={markSold} className="btn-ghost !py-2 !text-xs">Mark Sold</button>}
      {a.aotw && <div className="badge-lime">Featured</div>}
      <Link to={`/artwork/${a.id}`} className="label-caps hover:text-[#CCFF00]"><ExternalLink size={12} className="inline" /></Link>
      {a.status !== "sold" && <button data-testid={`delete-${a.id}`} onClick={del} className="text-zinc-500 hover:text-[#FF4D4D]"><Trash2 size={14} /></button>}
    </div>
  );
}

// ---------- Commission Requests Panel (artist inbox in Studio) ----------
function CommissionRequestsPanel() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);
  const [counterAmt, setCounterAmt] = useState("");
  const [counterMsg, setCounterMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/commissions/mine?as_role=artist").then((r) => setItems(r.data)).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const respond = async (id, action, extra = {}) => {
    setBusy(true);
    try {
      await api.post(`/commissions/${id}/respond`, { action, ...extra });
      toast.success(action === "accept" ? "Accepted" : action === "decline" ? "Declined" : "Counter sent");
      setOpenId(null); setCounterAmt(""); setCounterMsg("");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  const statusColor = { pending: "#F5A623", counter: "#F5A623", in_progress: "#7C3AED", accepted: "#CCFF00", declined: "#FF4D4D", delivered: "#00E5FF", approved: "#CCFF00", cancelled: "#52525B" };

  if (loading) return <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div>;
  if (items.length === 0) return (
    <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
      <div className="label-caps text-zinc-500">No commission requests yet.</div>
      <div className="text-sm text-zinc-400 mt-3">Collectors can request custom work from your Studio page.</div>
    </div>
  );
  return (
    <div data-testid="requests-panel" className="space-y-3">
      {items.map((c) => {
        const isOpen = openId === c.id;
        const canAct = c.status === "pending";
        return (
          <div key={c.id} data-testid={`request-${c.id}`} className="border border-white/8 rounded-sm">
            <div className="p-4 flex flex-wrap items-center gap-4">
              <div className="flex-1 min-w-[220px]">
                <div className="font-unbounded font-semibold text-lg">{c.subject}</div>
                <div className="text-sm text-zinc-400 mt-1 line-clamp-1">{c.instructions}</div>
                <div className="label-caps mt-2">From <span className="text-white">{c.buyer?.name}</span> · {new Date(c.created_at).toLocaleDateString()}</div>
              </div>
              <div className="text-right">
                <div className="font-anton text-2xl text-[#CCFF00]">${Number(c.counter_amount || c.budget).toLocaleString()}</div>
                <div className="label-caps mt-1" style={{ color: statusColor[c.status] || "#A1A1AA" }}>{c.status.replace(/_/g, " ")}</div>
              </div>
              <Link to={`/commissions/${c.id}`} className="label-caps hover:text-[#CCFF00]">Open →</Link>
              {canAct && (
                <button data-testid={`req-toggle-${c.id}`} onClick={() => setOpenId(isOpen ? null : c.id)} className="btn-ghost !py-2 !text-xs">
                  {isOpen ? "Close" : "Respond"}
                </button>
              )}
            </div>
            {isOpen && canAct && (
              <div className="p-4 border-t border-white/8 bg-white/[0.02] space-y-3">
                <div className="flex flex-wrap gap-2">
                  <button data-testid={`req-accept-${c.id}`} disabled={busy} onClick={() => respond(c.id, "accept")} className="btn-lime !py-2 !text-xs">Accept ${Number(c.budget).toLocaleString()}</button>
                  <button data-testid={`req-decline-${c.id}`} disabled={busy} onClick={() => respond(c.id, "decline")} className="btn-ghost !py-2 !text-xs">Decline</button>
                </div>
                <div className="border-t border-white/8 pt-3">
                  <div className="label-caps mb-2">Counter offer</div>
                  <div className="grid grid-cols-2 gap-2">
                    <input data-testid={`req-counter-amt-${c.id}`} type="number" min="1" placeholder="Amount" value={counterAmt} onChange={(e) => setCounterAmt(e.target.value)}
                      className="bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none" />
                    <input data-testid={`req-counter-msg-${c.id}`} placeholder="Message (optional)" value={counterMsg} onChange={(e) => setCounterMsg(e.target.value)}
                      className="bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none" />
                  </div>
                  <button data-testid={`req-counter-${c.id}`} disabled={busy || !counterAmt} onClick={() => respond(c.id, "counter", { counter_amount: Number(counterAmt), message: counterMsg })} className="btn-violet !py-2 !text-xs mt-2">Send Counter</button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
