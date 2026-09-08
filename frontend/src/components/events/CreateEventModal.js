import React, { useState } from "react";
import { X, Loader2, Search, Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../api";

const inputCls = "bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm";

export function CreateEventModal({ onClose, onCreated, categories = [] }) {
  const CATEGORIES = categories;
  const [form, setForm] = useState({
    title: "", description: "", category: "gallery_opening",
    address: "", city: "", lat: "", lng: "",
    start_at: "", end_at: "",
    is_free: true, ticket_price: "",
    cover_image: null, images: [],
    venue: "", organizer: "", website: "", ticket_info: "", ticket_url: "", tags: "",
    // recurrence
    recurring: false, freq: "weekly", count: 4,
    reminders_enabled: true,
  });
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [geocoding, setGeocoding] = useState(false);

  const setF = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setF("cover_image", r.data.path);
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const uploadGallery = async (files) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files).slice(0, 6)) {
        const fd = new FormData(); fd.append("file", file);
        const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setForm((f) => ({ ...f, images: [...f.images, r.data.path].slice(0, 8) }));
      }
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const geocode = async () => {
    const query = [form.address, form.city].filter(Boolean).join(", ");
    if (!query.trim()) { toast.error("Enter an address or city first"); return; }
    setGeocoding(true);
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`,
        { headers: { "Accept": "application/json" } });
      const data = await r.json();
      if (data && data[0]) {
        setF("lat", parseFloat(data[0].lat).toFixed(6));
        setF("lng", parseFloat(data[0].lon).toFixed(6));
        toast.success("Location found");
      } else {
        toast.error("Couldn't find that place");
      }
    } catch { toast.error("Geocoding failed"); }
    setGeocoding(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.title || !form.description || !form.start_at || !form.lat || !form.lng) {
      toast.error("Fill title, description, start time, and location");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: form.title,
        description: form.description,
        category: form.category,
        location: {
          lat: parseFloat(form.lat), lng: parseFloat(form.lng),
          address: form.address || null, city: form.city || null,
        },
        start_at: new Date(form.start_at).toISOString(),
        end_at: form.end_at ? new Date(form.end_at).toISOString() : null,
        cover_image: form.cover_image,
        images: form.images,
        venue: form.venue || null, organizer: form.organizer || null, website: form.website || null,
        ticket_info: form.ticket_info || null, ticket_url: form.ticket_url || null,
        tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
        is_free: form.is_free,
        ticket_price: form.is_free ? null : parseFloat(form.ticket_price) || 0,
        recurrence: form.recurring ? { frequency: form.freq, count: Math.max(2, Math.min(26, Number(form.count) || 2)) } : null,
        reminders_enabled: form.reminders_enabled,
      };
      await api.post("/events", payload);
      toast.success("Event created");
      onCreated();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
    setSaving(false);
  };

  return (
    <div data-testid="create-event-modal" onClick={onClose}
      className="fixed inset-0 z-[1200] bg-black/80 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div onClick={(e) => e.stopPropagation()} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-2xl my-auto">
        <div className="flex items-center justify-between p-4 border-b border-white/8">
          <div className="font-unbounded font-semibold">Host an event</div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="p-4 space-y-4">
          <input data-testid="event-title" placeholder="Title" value={form.title} onChange={(e) => setF("title", e.target.value)}
            className="w-full bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00]" />
          <textarea data-testid="event-description" placeholder="Describe the vibe, what people can expect..." rows={4}
            value={form.description} onChange={(e) => setF("description", e.target.value)}
            className="w-full bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm resize-none" />
          <div className="grid grid-cols-2 gap-3">
            <select data-testid="event-category" value={form.category} onChange={(e) => setF("category", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm">
              {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            <label className="btn-ghost !py-3 cursor-pointer text-center flex items-center justify-center gap-2 text-xs">
              {uploading ? <Loader2 size={14} className="animate-spin" /> : (form.cover_image ? "Change cover" : "Cover image")}
              <input data-testid="event-cover" type="file" accept="image/*" className="hidden"
                onChange={(e) => upload(e.target.files?.[0])} />
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input data-testid="event-address" placeholder="Address" value={form.address} onChange={(e) => setF("address", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            <input data-testid="event-city" placeholder="City" value={form.city} onChange={(e) => setF("city", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input data-testid="event-venue" placeholder="Venue name (e.g. Bushwick Collective)" value={form.venue} onChange={(e) => setF("venue", e.target.value)} className={inputCls} />
            <input data-testid="event-organizer" placeholder="Organizer (defaults to you)" value={form.organizer} onChange={(e) => setF("organizer", e.target.value)} className={inputCls} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input data-testid="event-website" placeholder="Website (optional)" value={form.website} onChange={(e) => setF("website", e.target.value)} className={inputCls} />
            <input data-testid="event-tags" placeholder="Tags, comma separated (murals, opening night)" value={form.tags} onChange={(e) => setF("tags", e.target.value)} className={inputCls} />
          </div>
          <label className="btn-ghost !py-2.5 cursor-pointer text-center flex items-center justify-center gap-2 text-xs">
            {uploading ? <Loader2 size={14} className="animate-spin" /> : `Gallery photos${form.images.length ? ` (${form.images.length})` : ""}`}
            <input data-testid="event-gallery" type="file" accept="image/*" multiple className="hidden" onChange={(e) => uploadGallery(e.target.files)} />
          </label>
          <button type="button" data-testid="event-geocode" onClick={geocode}
            className="btn-ghost !py-2 !text-xs w-full flex items-center justify-center gap-2">
            {geocoding ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
            Find coordinates from address
          </button>
          <div className="grid grid-cols-2 gap-3">
            <input data-testid="event-lat" placeholder="Latitude" value={form.lat} onChange={(e) => setF("lat", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            <input data-testid="event-lng" placeholder="Longitude" value={form.lng} onChange={(e) => setF("lng", e.target.value)}
              className="bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-zinc-500 mb-1">Start</div>
              <input data-testid="event-start" type="datetime-local" value={form.start_at} onChange={(e) => setF("start_at", e.target.value)}
                className="w-full bg-white/[0.03] border border-white/12 px-3 py-2.5 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            </div>
            <div>
              <div className="text-xs text-zinc-500 mb-1">End (optional)</div>
              <input data-testid="event-end" type="datetime-local" value={form.end_at} onChange={(e) => setF("end_at", e.target.value)}
                className="w-full bg-white/[0.03] border border-white/12 px-3 py-2.5 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input data-testid="event-ticket-info" placeholder="Ticket info (e.g. $15 at the door, members free)" value={form.ticket_info} onChange={(e) => setF("ticket_info", e.target.value)} className={inputCls} />
            <input data-testid="event-ticket-url" placeholder="External ticket link (optional)" value={form.ticket_url} onChange={(e) => setF("ticket_url", e.target.value)} className={inputCls} />
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input data-testid="event-free" type="checkbox" checked={form.is_free} onChange={(e) => setF("is_free", e.target.checked)} />
            Free event
          </label>
          {!form.is_free && (
            <input data-testid="event-price" type="number" step="0.01" placeholder="Ticket price"
              value={form.ticket_price} onChange={(e) => setF("ticket_price", e.target.value)}
              className="w-full bg-white/[0.03] border border-white/12 px-3 py-3 rounded-sm outline-none focus:border-[#CCFF00] text-sm" />
          )}
          <div className="border-t border-white/8 pt-3 space-y-3">
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <input data-testid="event-recurring" type="checkbox" checked={form.recurring}
                onChange={(e) => setF("recurring", e.target.checked)} />
              Make it a recurring series
            </label>
            {form.recurring && (
              <div className="grid grid-cols-2 gap-3">
                <select data-testid="event-freq" value={form.freq} onChange={(e) => setF("freq", e.target.value)}
                  className="bg-white/[0.03] border border-white/12 px-3 py-2.5 rounded-sm text-sm outline-none focus:border-[#CCFF00]">
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Biweekly</option>
                  <option value="monthly">Monthly</option>
                </select>
                <input data-testid="event-count" type="number" min="2" max="26" placeholder="How many total?"
                  value={form.count} onChange={(e) => setF("count", e.target.value)}
                  className="bg-white/[0.03] border border-white/12 px-3 py-2.5 rounded-sm text-sm outline-none focus:border-[#CCFF00]" />
                <div className="col-span-2 text-xs text-zinc-500">
                  Creates {Math.max(2, Math.min(26, Number(form.count) || 2))} events, each {form.freq === "weekly" ? "7" : form.freq === "biweekly" ? "14" : "30"} days apart.
                </div>
              </div>
            )}
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <input data-testid="event-reminders" type="checkbox" checked={form.reminders_enabled}
                onChange={(e) => setF("reminders_enabled", e.target.checked)} />
              Send 24h + 1h reminders to attendees{form.recurring ? " (every occurrence)" : ""}
            </label>
          </div>
          <button data-testid="event-submit" type="submit" disabled={saving}
            className="btn-lime w-full !py-3 flex items-center justify-center gap-2">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Create event
          </button>
        </form>
      </div>
    </div>
  );
}
