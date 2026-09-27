/**
 * Studio Editor building blocks — extracted from pages/StudioEditor.js for maintainability.
 * All logic and data-testids preserved verbatim from the original.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../../api";
import { toast } from "sonner";
import { Sparkles, GripVertical, Trash2, ExternalLink, ShieldCheck } from "lucide-react";
import { MySchoolCard } from "./MySchoolCard";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

// ---------- Section header ----------
export function SectionH({ title, children }) {
  return (
    <div>
      <div className="label-caps mb-4">{title}</div>
      {children}
    </div>
  );
}

// ---------- Stat card ----------
export function Stat({ label, value, accent }) {
  return (
    <div className="glass-card p-5 rounded-sm">
      <div className="label-caps">{label}</div>
      <div className="font-anton text-4xl mt-3" style={{ color: accent }}>{value}</div>
    </div>
  );
}

// ---------- Background editor (theme / upload / solid color + texture overlay) ----------
export function BackgroundEditor({ config, save }) {
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

// ---------- Polish button (Claude rewrite) ----------
export function PolishButton({ value, kind, onApply, testId }) {
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const run = async () => {
    if (!value || value.trim().length < 3) { toast("Add a few words first"); return; }
    setBusy(true);
    try {
      const r = await api.post("/studio/polish-text", { body: value, kind });
      setPreview({ original: value, polished: r.data.polished });
    } catch (e) { toast.error(e?.response?.data?.detail || "Polish failed"); }
    setBusy(false);
  };
  const accept = () => { onApply(preview.polished); setPreview(null); toast.success("Polished text applied"); };
  const decline = () => setPreview(null);
  return (
    <>
      <button type="button" data-testid={testId} onClick={run} disabled={busy}
        className="label-caps text-xs px-2 py-1 border border-[#7C3AED]/40 text-[#7C3AED] hover:bg-[#7C3AED]/10 rounded-sm inline-flex items-center gap-1 transition-colors">
        <Sparkles size={11} /> {busy ? "Polishing..." : "Polish"}
      </button>
      {preview && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={decline} data-testid={`${testId}-preview`}>
          <div className="glass-card max-w-2xl w-full rounded-sm p-6 md:p-8" onClick={(e) => e.stopPropagation()}>
            <div className="label-caps text-[#7C3AED] flex items-center gap-2"><Sparkles size={14} /> Polished by Claude</div>
            <div className="mt-5 space-y-4">
              <div>
                <div className="label-caps text-zinc-500 mb-2">Before</div>
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-sm text-sm text-zinc-400 whitespace-pre-wrap">{preview.original}</div>
              </div>
              <div>
                <div className="label-caps text-[#CCFF00] mb-2">After</div>
                <div className="p-4 bg-[#CCFF00]/5 border border-[#CCFF00]/30 rounded-sm text-sm text-white whitespace-pre-wrap">{preview.polished}</div>
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button data-testid={`${testId}-accept`} onClick={accept} className="btn-lime flex-1">Use This</button>
              <button data-testid={`${testId}-decline`} onClick={decline} className="btn-ghost">Keep Original</button>
              <button data-testid={`${testId}-retry`} onClick={run} disabled={busy} className="btn-ghost">
                {busy ? "..." : "Try Again"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ---------- Templates picker ----------
export function TemplatesPicker({ save }) {
  const [templates, setTemplates] = useState([]);
  const [busy, setBusy] = useState(null);
  useEffect(() => { api.get("/studio/templates").then((r) => setTemplates(r.data)); }, []);
  const apply = async (t) => {
    if (!confirm(`Apply the "${t.name}" template? This will replace your current sections and theme in draft — you can still Preview + Publish or Discard.`)) return;
    setBusy(t.id);
    try {
      await api.post("/studio/apply-template", { template_id: t.id });
      toast.success(`${t.name} applied to draft`);
      if (save) save({});
      window.location.reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };
  return (
    <div data-testid="templates-picker" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {templates.map((t) => (
        <button key={t.id} data-testid={`template-${t.id}`} onClick={() => apply(t)}
          disabled={busy === t.id}
          className="glass-card p-5 rounded-sm text-left hover-lift-card border border-white/8 relative overflow-hidden">
          <div className="absolute -top-8 -right-8 w-24 h-24 rounded-full blur-2xl opacity-40" style={{ background: t.accent }} />
          <div className="relative">
            <div className="label-caps text-xs" style={{ color: t.accent }}>{t.vibe}</div>
            <div className="font-anton text-2xl uppercase mt-2">{t.name}</div>
            <div className="text-sm text-zinc-400 mt-3 leading-relaxed">{t.description}</div>
            <div className="mt-4 label-caps text-zinc-500">{busy === t.id ? "Applying..." : "Apply →"}</div>
          </div>
        </button>
      ))}
    </div>
  );
}

// ---------- Section kinds + layouts ----------
export const SECTION_KINDS = [
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

export const LAYOUT_OPTIONS = [
  { id: "grid", label: "Grid" },
  { id: "masonry", label: "Masonry" },
  { id: "salon", label: "Salon Wall" },
  { id: "showcase", label: "Single Showcase" },
  { id: "carousel", label: "Carousel" },
];

// ---------- Image block editor ----------
export function ImageBlockEditor({ s, update }) {
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

// ---------- Sections editor (drag-drop + inline editors) ----------
export function SectionsEditor({ config, save }) {
  const sections = config.sections || [];
  const [expanded, setExpanded] = useState(null);
  const [dragIdx, setDragIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);
  const sorted = [...sections].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  const move = (i, dir) => {
    const arr = [...sorted];
    const j = i + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    arr.forEach((s, idx) => (s.order = idx));
    save({ sections: arr });
  };
  const reorderTo = (from, to) => {
    if (from === to || from == null) return;
    const arr = [...sorted];
    const [moved] = arr.splice(from, 1);
    arr.splice(to, 0, moved);
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
      <div className="text-xs text-zinc-500 mb-2">💡 Drag rows to reorder · Click <span className="text-[#CCFF00]">Edit</span> to customize each section.</div>
      <div className="border border-white/8 rounded-sm divide-y divide-white/8">
        {sorted.map((s, i) => {
          const meta = SECTION_KINDS.find((k) => k.kind === s.kind);
          const isExpanded = expanded === s.id;
          const canExpand = ["custom", "text_block", "announcement", "button_cta", "image_block"].includes(s.kind) || meta?.gallery;
          const isDragging = dragIdx === i;
          const isDragOver = dragOverIdx === i && dragIdx !== null && dragIdx !== i;
          return (
            <div key={s.id} data-testid={`section-row-${s.id}`}
              draggable
              onDragStart={(e) => { setDragIdx(i); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); }}
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOverIdx(i); }}
              onDragLeave={() => setDragOverIdx((v) => (v === i ? null : v))}
              onDrop={(e) => { e.preventDefault(); const from = Number(e.dataTransfer.getData("text/plain")); reorderTo(from, i); setDragIdx(null); setDragOverIdx(null); }}
              onDragEnd={() => { setDragIdx(null); setDragOverIdx(null); }}
              className={`transition-all ${isDragging ? "opacity-40" : ""} ${isDragOver ? "bg-[#CCFF00]/10 border-t-2 border-t-[#CCFF00]" : ""}`}
              style={{ cursor: "move" }}>
              <div className="p-4 flex flex-wrap items-center gap-3">
                <GripVertical size={16} className="text-zinc-500 cursor-grab active:cursor-grabbing" />
                <div className="label-caps text-zinc-500 w-32 flex-shrink-0 truncate">{s.kind}</div>
                <input value={s.title} onChange={(e) => update(s.id, { title: e.target.value })}
                  onDragStart={(e) => e.stopPropagation()}
                  draggable={false}
                  className="flex-1 min-w-[180px] bg-transparent border-b border-white/10 focus:border-[#CCFF00] px-2 py-1 outline-none" />
                <label className="label-caps flex items-center gap-2" onDragStart={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={s.visible !== false} onChange={(e) => update(s.id, { visible: e.target.checked })} /> Visible
                </label>
                <button onClick={() => move(i, -1)} title="Move up" className="label-caps hover:text-[#CCFF00] hidden md:inline">↑</button>
                <button onClick={() => move(i, 1)} title="Move down" className="label-caps hover:text-[#CCFF00] hidden md:inline">↓</button>
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
                      <div className="flex items-center justify-between mb-2">
                        <div className="label-caps">Body</div>
                        <PolishButton
                          testId={`polish-body-${s.id}`}
                          value={s.body || ""}
                          kind={s.kind}
                          onApply={(text) => update(s.id, { body: text })} />
                      </div>
                      <textarea data-testid={`body-${s.id}`} rows={s.kind === "announcement" ? 3 : 6}
                        value={s.body || ""} onChange={(e) => update(s.id, { body: e.target.value })}
                        onDragStart={(e) => e.stopPropagation()}
                        draggable={false}
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
                        <div className="flex items-center justify-between mb-2">
                          <div className="label-caps">Blurb</div>
                          <PolishButton
                            testId={`polish-blurb-${s.id}`}
                            value={s.body || ""}
                            kind="button_cta"
                            onApply={(text) => update(s.id, { body: text })} />
                        </div>
                        <textarea rows={2} value={s.body || ""} onChange={(e) => update(s.id, { body: e.target.value })}
                          onDragStart={(e) => e.stopPropagation()} draggable={false}
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

// ---------- Featured artwork picker ----------
export function FeaturedEditor({ config, save, artworks }) {
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
        <div className="text-sm text-zinc-400 mt-2">Pick up to 12 pieces to spotlight in the Featured Works section (in the exact order you tap them). Leave empty to show the artworks you&apos;ve flagged as Featured elsewhere.</div>
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
export function StoryEditor({ config, save, user, refresh }) {
  const [story, setStory] = useState(config.artist_story || {});
  const [bio, setBio] = useState(user.bio || "");
  const [saving, setSaving] = useState(false);

  const configStoryKey = JSON.stringify(config.artist_story || {});
  useEffect(() => { setStory(config.artist_story || {}); }, [configStoryKey]);
  useEffect(() => { setBio(user.bio || ""); }, [user.bio]);

  const patch = (k, v) => setStory((prev) => ({ ...prev, [k]: v }));
  const saveAll = async () => {
    setSaving(true);
    try {
      await save({ artist_story: story });
      await api.patch("/auth/me", { bio });
      await refresh();
      toast.success("Story saved to draft — hit Publish to make it live");
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    setSaving(false);
  };

  const [avatarBusy, setAvatarBusy] = useState(false);
  const uploadAvatar = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setAvatarBusy(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      await api.patch("/auth/me", { avatar: r.data.path });
      await refresh();
      toast.success("Photo updated — it's live on your Studio right away");
    } catch { toast.error("Upload failed"); }
    setAvatarBusy(false);
  };
  const removeAvatar = async () => {
    try { await api.patch("/auth/me", { avatar: null }); await refresh(); toast.success("Photo removed"); } catch { toast.error("Failed"); }
  };

  const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]";
  return (
    <div className="space-y-5 max-w-3xl">
      <div className="glass-card rounded-sm p-5 flex flex-col sm:flex-row items-start sm:items-center gap-5" data-testid="avatar-editor">
        <div className="avatar-ring w-24 h-24 shrink-0">
          {user.avatar
            ? <img src={fileUrl(user.avatar)} alt={user.name} data-testid="avatar-preview" className="w-full h-full object-cover rounded-full" />
            : <div className="bg-[#0A0A0C] rounded-full w-full h-full flex items-center justify-center font-anton text-3xl uppercase" data-testid="avatar-initial">{user.name?.[0]}</div>}
        </div>
        <div className="flex-1">
          <div className="label-caps">Your photo</div>
          <div className="text-sm text-zinc-400 mt-1">Show collectors who they're buying from. A clear face shot or you in the studio works best. Square, at least 400×400.</div>
          <div className="flex flex-wrap gap-3 mt-3">
            <label className="btn-lime !py-2 !text-xs cursor-pointer">
              {avatarBusy ? "Uploading..." : user.avatar ? "Change photo" : "Upload photo"}
              <input data-testid="avatar-input" type="file" accept="image/*" onChange={uploadAvatar} className="hidden" disabled={avatarBusy} />
            </label>
            {user.avatar && <button type="button" data-testid="avatar-remove" onClick={removeAvatar} className="btn-ghost !py-2 !text-xs">Remove</button>}
          </div>
        </div>
      </div>
      <label className="block">
        <div className="flex items-center justify-between mb-2">
          <div className="label-caps">Bio (shown at top of your Studio)</div>
          <PolishButton testId="polish-bio" value={bio} kind="text_block" onApply={(t) => setBio(t)} />
        </div>
        <textarea data-testid="bio-input" value={bio} onChange={(e) => setBio(e.target.value)} rows={4}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
      </label>
      <MySchoolCard user={user} refresh={refresh} />
      <div className="grid md:grid-cols-2 gap-4">
        <label className="block"><div className="label-caps mb-2">Location</div><input data-testid="story-location" value={story.location || ""} onChange={(e) => patch("location", e.target.value)} className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Style</div><input data-testid="story-style" value={story.style || ""} onChange={(e) => patch("style", e.target.value)} placeholder="Abstract, street, mixed media..." className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Active since (year)</div><input data-testid="story-years" value={story.years_active || ""} onChange={(e) => patch("years_active", e.target.value)} className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Education</div><input data-testid="story-education" value={story.education || ""} onChange={(e) => patch("education", e.target.value)} className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Exhibitions</div><input data-testid="story-exhibitions" value={story.exhibitions || ""} onChange={(e) => patch("exhibitions", e.target.value)} className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Awards</div><input data-testid="story-awards" value={story.awards || ""} onChange={(e) => patch("awards", e.target.value)} className={inputCls} /></label>
      </div>
      <label className="block">
        <div className="flex items-center justify-between mb-2">
          <div className="label-caps">Influences / Inspiration</div>
          <PolishButton testId="polish-influences" value={story.influences || ""} kind="text_block" onApply={(t) => patch("influences", t)} />
        </div>
        <textarea data-testid="story-influences" value={story.influences || ""} onChange={(e) => patch("influences", e.target.value)} rows={3}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
      </label>
      <div className="grid md:grid-cols-3 gap-4">
        <label className="block"><div className="label-caps mb-2">Website</div><input data-testid="story-website" value={story.website || ""} onChange={(e) => patch("website", e.target.value)} placeholder="https://" className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Instagram</div><input data-testid="story-instagram" value={story.instagram || ""} onChange={(e) => patch("instagram", e.target.value)} placeholder="@handle" className={inputCls} /></label>
        <label className="block"><div className="label-caps mb-2">Twitter / X</div><input data-testid="story-twitter" value={story.twitter || ""} onChange={(e) => patch("twitter", e.target.value)} placeholder="@handle" className={inputCls} /></label>
      </div>
      <button data-testid="save-story" onClick={saveAll} disabled={saving} className="btn-lime mt-4">
        {saving ? "Saving..." : "Save Story"}
      </button>
    </div>
  );
}

// ---------- Posts editor ----------
export function PostsEditor({ userId }) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState("update");
  const [image, setImage] = useState(null);
  const [video, setVideo] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [posts, setPosts] = useState([]);
  const load = () => api.get(`/posts?artist_id=${userId}`).then((r) => setPosts(r.data));
  useEffect(() => { load(); }, []);

  const uploadImage = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImage(r.data.path); setVideo(null);
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };
  const uploadVideo = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 60 * 1024 * 1024) { toast.error("Video too large — max 60MB"); return; }
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/video", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setVideo(r.data.path); setImage(null);
    } catch (er) { toast.error(er?.response?.data?.detail || "Upload failed"); }
    setUploading(false);
  };
  const post = async () => {
    if (!text.trim()) return;
    try {
      await api.post("/posts", { text, kind, image, video });
      setText(""); setImage(null); setVideo(null); toast.success("Posted"); load();
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
            <option value="behind_scenes">Behind the scenes</option>
            <option value="announcement">Announcement</option>
            <option value="auction">Auction</option>
            <option value="sold">Sold</option>
            <option value="commission">Commission</option>
            <option value="exhibition">Exhibition</option>
            <option value="event">Event</option>
          </select>
          <div className="flex gap-2">
            <label className="label-caps text-xs px-2 py-2 border border-white/12 rounded-sm cursor-pointer hover:border-[#CCFF00] flex-1 text-center">
              📷 Photo
              <input data-testid="post-image-upload" type="file" accept="image/*" onChange={uploadImage} className="hidden" />
            </label>
            <label className="label-caps text-xs px-2 py-2 border border-white/12 rounded-sm cursor-pointer hover:border-[#7C3AED] flex-1 text-center">
              🎥 Video
              <input data-testid="post-video-upload" type="file" accept="video/mp4,video/webm,video/quicktime" onChange={uploadVideo} className="hidden" />
            </label>
          </div>
        </div>
        <textarea data-testid="post-text" value={text} onChange={(e) => setText(e.target.value)} rows={4}
          placeholder="What's happening in the studio? Use @name to tag." className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
        {image && <img src={fileUrl(image)} className="mt-3 w-40 rounded-sm" alt="" />}
        {video && (
          <div className="mt-3 flex items-center gap-3">
            <video src={fileUrl(video)} className="w-40 rounded-sm" controls muted />
            <button onClick={() => setVideo(null)} className="label-caps text-[#FF4D4D] hover:underline text-xs">Remove</button>
          </div>
        )}
        {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
        <button data-testid="post-create" disabled={uploading} onClick={post} className="btn-lime mt-4">Publish</button>
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
            {p.video ? (
              <video src={resolveImg(p.video)} className="mt-3 w-full max-w-md rounded-sm" controls preload="metadata" />
            ) : p.image ? (
              <img src={resolveImg(p.image)} className="mt-3 w-64 rounded-sm" alt="" />
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Payouts panel (Stripe Connect) ----------
function FeePreview() {
  const [gross, setGross] = useState(100);
  const [split, setSplit] = useState(null);
  useEffect(() => {
    const t = setTimeout(async () => {
      try { const r = await api.get("/settings/fee-preview", { params: { gross: Number(gross) || 0 } }); setSplit(r.data); } catch { /* ignore */ }
    }, 250);
    return () => clearTimeout(t);
  }, [gross]);
  const money = (v) => `$${Number(v || 0).toFixed(2)}`;
  return (
    <div className="mt-4 p-4 rounded-sm bg-white/[0.03] border border-white/10 max-w-lg" data-testid="fee-preview">
      <div className="label-caps text-zinc-400 mb-2">What you'd keep on a sale of</div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-zinc-500">$</span>
        <input data-testid="fee-preview-input" type="number" min="0" step="1" value={gross} onChange={(e) => setGross(e.target.value)}
          className="w-28 bg-transparent border border-white/12 rounded-sm px-2 py-1 outline-none text-sm" />
      </div>
      {split && (
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div><div className="text-zinc-500">Art Core fee ({split.commission_percent}%{split.founding_locked ? " · locked" : ""}{split.fee_waived ? " · 0% window" : ""})</div><div className="font-unbounded text-zinc-300" data-testid="fee-preview-platform">-{money(split.platform_take)}</div></div>
          <div><div className="text-zinc-500">Card processing</div><div className="font-unbounded text-zinc-300" data-testid="fee-preview-processing">-{money(split.processing_fee)}</div></div>
          <div><div className="text-zinc-500">You receive</div><div className="font-unbounded text-[#CCFF00]" data-testid="fee-preview-net">{money(split.net)}</div></div>
        </div>
      )}
    </div>
  );
}

export function PayoutsPanel({ dashboard, refresh, refreshUser }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const loadStatus = async () => {
    try { const r = await api.get("/connect/status"); setStatus(r.data); }
    catch { /* ignore */ }
  };
  useEffect(() => { loadStatus(); }, []);

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
            <div className="text-xs text-zinc-500 mt-3 max-w-lg" data-testid="fee-explainer">
              Art Core uses Stripe Connect Express to route your share of each sale directly to your bank. On every sale you keep everything except Art Core's platform fee and Stripe's standard card processing (~2.9% + 30¢) — no listing fees, no subscriptions.
            </div>
            <FeePreview />
            <Link to="/security" data-testid="payouts-2fa-link" className="mt-4 inline-flex items-center gap-2 text-xs text-[#F5A623] hover:text-white transition-colors">
              <ShieldCheck size={12} /> Protect your payouts — turn on two-factor login →
            </Link>
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

      <div className="mb-10" data-testid="upcoming-payouts">
        <div className="label-caps text-zinc-400 mb-3">Upcoming payouts</div>
        <div className="text-xs text-zinc-500 mb-4 max-w-2xl">
          Money is released <span className="text-zinc-300">{dashboard.payout_policy?.delivery_delay_days ?? 2} days after the collector confirms delivery</span>, or automatically {dashboard.payout_policy?.hold_business_days ?? 10} business days after the sale if they never confirm.
          Ship with tracking — it's required — so buyers can confirm fast.{dashboard.payout_policy && <> Pro members release same-day on delivery with a {dashboard.payout_policy.pro_hold_business_days}-day hold.</>}
        </div>
        {(dashboard.upcoming_payouts || []).length === 0 ? <div className="text-zinc-600 text-xs" data-testid="no-upcoming-payouts">Nothing in the pipeline right now.</div> : (
          <div className="border border-white/8 rounded-sm divide-y divide-white/8">
            {dashboard.upcoming_payouts.map((u) => (
              <div key={u.order_id} className="p-3 flex items-center justify-between gap-3 text-sm" data-testid={`upcoming-payout-${u.order_id}`}>
                <div className="min-w-0">
                  <div className="font-unbounded text-[#CCFF00]">${Number(u.net).toFixed(2)}</div>
                  <div className="text-[10px] text-zinc-500 mt-0.5">Order {u.order_id.slice(0, 8)} · {u.hold_reason === "delivered" ? "Delivery confirmed" : u.fulfillment === "shipped" ? "Shipped · awaiting confirmation" : "Awaiting shipment"}</div>
                </div>
                <div className="text-right"><div className="label-caps text-[10px] text-zinc-400">Releases</div><div className="text-xs" data-testid="upcoming-release-date">{u.release_at ? new Date(u.release_at).toLocaleDateString() : "—"}</div></div>
              </div>
            ))}
          </div>
        )}
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

// ---------- Artwork row (in Artworks tab) ----------
export function ArtworkRow({ a, onReload, onPayFee, onSubmitAotw }) {
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

// ---------- Commission Requests Panel ----------
export function CommissionRequestsPanel() {
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
              <div className="p-4 border-t border-white/8 bg-white/[0.02] space-y-3" data-testid={`respond-${c.id}`}>
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
