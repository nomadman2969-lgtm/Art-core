import React, { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { Bookmark, Plus, Trash2, X, Lock } from "lucide-react";
import { EmptyState } from "../components/EmptyState";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function SavedIndex() {
  const [cols, setCols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/collections/mine").then((r) => setCols(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const create = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.post("/collections", { name, description: description || undefined, is_private: isPrivate });
      toast.success("Collection created");
      setCreating(false); setName(""); setDescription(""); setIsPrivate(false);
      load();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    if (!confirm("Delete this collection? Saved items stay in All Saved.")) return;
    try {
      await api.delete(`/collections/${id}`);
      toast.success("Deleted");
      load();
    } catch { toast.error("Failed"); }
  };

  return (
    <div data-testid="saved-index" className="max-w-5xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="flex items-end justify-between flex-wrap gap-4 mb-10">
        <div>
          <div className="label-caps text-[#CCFF00]"><Bookmark size={12} className="inline mr-2" /> Your Library</div>
          <h1 className="font-anton text-5xl md:text-7xl uppercase mt-3">Saved & Collections</h1>
        </div>
        <button data-testid="new-collection-btn" onClick={() => setCreating(true)} className="btn-lime"><Plus size={14} className="mr-2" /> New Collection</button>
      </div>

      {creating && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setCreating(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={create} className="glass-card max-w-md w-full p-6 rounded-sm space-y-4">
            <div className="flex items-center justify-between">
              <div className="label-caps text-[#CCFF00]">New Collection</div>
              <button type="button" onClick={() => setCreating(false)} className="text-zinc-500 hover:text-white"><X size={18} /></button>
            </div>
            <label className="block">
              <div className="label-caps mb-2">Name</div>
              <input data-testid="col-name" required autoFocus value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Living room wall, Gift ideas..."
                className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
            </label>
            <label className="block">
              <div className="label-caps mb-2">Description (optional)</div>
              <textarea data-testid="col-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
                className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#CCFF00]" />
            </label>
            <label className="flex items-center gap-2 label-caps">
              <input data-testid="col-private" type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} /> Keep private
            </label>
            <div className="flex gap-2 pt-2">
              <button data-testid="col-create" type="submit" className="btn-lime flex-1">Create</button>
              <button type="button" onClick={() => setCreating(false)} className="btn-ghost">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        cols.length === 1 && cols[0].item_count === 0 ? (
          <EmptyState icon="bookmark" title="Nothing saved yet" body="Tap the bookmark on any artwork to keep it here. Make collections like “For the studio” or “Gift ideas” and share them." cta="Browse the Marketplace" to="/marketplace" testId="saved-empty" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {cols.map((c) => (
              <Link key={c.id} to={`/saved/${c.id}`} data-testid={`col-${c.id}`}
                className="glass-card rounded-sm overflow-hidden hover-lift-card relative">
                <div className="aspect-[4/3] grid grid-cols-3 gap-0.5 bg-black relative">
                  {c.covers.length === 0 ? (
                    <div className="col-span-3 flex items-center justify-center">
                      <Bookmark size={32} className="text-zinc-700" />
                    </div>
                  ) : c.covers.map((p, i) => (
                    <div key={i} className={i === 0 ? "col-span-2 row-span-2" : ""}>
                      <img src={resolveImg(p)} className="w-full h-full object-cover" alt="" />
                    </div>
                  ))}
                  {c.is_private && <div className="absolute top-2 right-2 label-caps flex items-center gap-1 bg-black/60 px-2 py-1 rounded-sm text-xs"><Lock size={10} /> Private</div>}
                </div>
                <div className="p-4 flex items-start justify-between">
                  <div className="min-w-0">
                    <div className="font-anton text-2xl uppercase truncate">{c.name}</div>
                    <div className="label-caps text-zinc-500 mt-1">{c.item_count} piece{c.item_count === 1 ? "" : "s"}</div>
                  </div>
                  {!c.is_all && (
                    <button data-testid={`col-delete-${c.id}`} onClick={(e) => { e.preventDefault(); remove(c.id); }} className="text-zinc-600 hover:text-[#FF4D4D]">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
    </div>
  );
}

export function CollectionDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get(`/collections/${id}`).then((r) => setData(r.data)).catch(() => nav("/saved")).finally(() => setLoading(false));
  }, [id]);
  if (loading) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  if (!data) return null;
  const { collection: c, items } = data;
  const unsave = async (aid) => {
    try {
      await api.delete(`/artworks/${aid}/save${c.id !== "all" ? `?collection_id=${c.id}` : ""}`);
      setData({ ...data, items: items.filter((i) => i.id !== aid) });
    } catch { toast.error("Failed"); }
  };
  return (
    <div data-testid="collection-detail" className="max-w-[1400px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <Link to="/saved" className="label-caps text-zinc-500 hover:text-[#CCFF00]">← All collections</Link>
      <div className="mt-6 mb-10">
        <div className="label-caps text-[#CCFF00]"><Bookmark size={12} className="inline mr-2" /> Collection</div>
        <h1 className="font-anton text-5xl md:text-7xl uppercase mt-3">{c.name}</h1>
        {c.description && <p className="text-zinc-300 mt-3 max-w-2xl">{c.description}</p>}
        <div className="label-caps text-zinc-500 mt-3">{items.length} piece{items.length === 1 ? "" : "s"}</div>
      </div>
      {items.length === 0 ? (
        <div className="border border-dashed border-white/10 py-24 text-center rounded-sm">
          <div className="label-caps text-zinc-500">Empty for now</div>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {items.map((a) => (
            <div key={a.id} data-testid={`col-item-${a.id}`} className="relative group">
              <Link to={`/artwork/${a.id}`} className="block border border-white/8 rounded-sm overflow-hidden hover-lift-card bg-black">
                <img src={resolveImg(a.images?.[0])} className="w-full aspect-square object-cover" alt={a.title} loading="lazy" />
                <div className="p-3">
                  <div className="font-unbounded font-semibold text-sm truncate">{a.title}</div>
                  <div className="text-xs text-zinc-500 mt-1">by {a.artist?.name}</div>
                  <div className="font-anton text-lg text-[#CCFF00] mt-1">${Number(a.price).toLocaleString()}</div>
                </div>
              </Link>
              <button data-testid={`unsave-${a.id}`} onClick={() => unsave(a.id)}
                className="absolute top-2 right-2 w-8 h-8 bg-black/80 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[#FF4D4D]">
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
