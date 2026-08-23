import React, { useState } from "react";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { X, Upload, Palette } from "lucide-react";

/**
 * Modal for collectors to submit a commission request from an artist's Studio.
 * Uses existing POST /api/commissions endpoint. Fields: subject, description,
 * budget, deadline, reference_images (upload). Notifies artist via existing
 * commission_request notification wiring.
 */
export default function CommissionRequestModal({ artist, onClose, onSubmitted }) {
  const [form, setForm] = useState({ subject: "", instructions: "", budget: 500, deadline: "" });
  const [refs, setRefs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);

  const upload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setRefs((prev) => [...prev, r.data.path]);
      }
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };
  const removeRef = (p) => setRefs((prev) => prev.filter((x) => x !== p));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.subject.trim() || !form.instructions.trim()) { toast.error("Add a subject and description"); return; }
    setBusy(true);
    try {
      const r = await api.post("/commissions", {
        artist_id: artist.id,
        subject: form.subject,
        instructions: form.instructions,
        budget: Number(form.budget),
        deadline: form.deadline || null,
        reference_images: refs,
      });
      toast.success(`Request sent to ${artist.name}`);
      onSubmitted?.(r.data);
      onClose();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  return (
    <div data-testid="commission-modal" className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto"
      onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="glass-card rounded-sm max-w-lg w-full my-8 border border-white/10">
        <div className="flex items-center justify-between p-5 border-b border-white/8">
          <div>
            <div className="label-caps text-[#CCFF00]"><Palette size={12} className="inline mr-2" /> Commission</div>
            <div className="font-anton text-2xl uppercase mt-1">Request from {artist.name}</div>
          </div>
          <button data-testid="modal-close" onClick={onClose} className="text-zinc-500 hover:text-white p-1"><X size={18} /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <label className="block">
            <div className="label-caps mb-2">Project subject</div>
            <input data-testid="modal-subject" required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
              placeholder="Portrait of my dog on a purple background"
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]" />
          </label>
          <label className="block">
            <div className="label-caps mb-2">Description</div>
            <textarea data-testid="modal-description" required rows={4} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })}
              placeholder="Style, size preferences, color palette, anything you want them to know..."
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm p-3 outline-none focus:border-[#CCFF00]" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <div className="label-caps mb-2">Budget (USD)</div>
              <input data-testid="modal-budget" type="number" min="1" required value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })}
                className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]" />
            </label>
            <label className="block">
              <div className="label-caps mb-2">Deadline (optional)</div>
              <input data-testid="modal-deadline" type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })}
                className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]" />
            </label>
          </div>
          <label className="block">
            <div className="label-caps mb-2">Reference images (optional)</div>
            <input data-testid="modal-refs" type="file" accept="image/*" multiple onChange={upload} className="text-sm" />
            {uploading && <div className="text-xs text-[#CCFF00] mt-2">Uploading...</div>}
            {refs.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {refs.map((p) => (
                  <div key={p} className="relative group">
                    <img src={fileUrl(p)} className="w-16 h-16 object-cover rounded-sm border border-white/8" alt="" />
                    <button type="button" onClick={() => removeRef(p)} className="absolute -top-1 -right-1 bg-[#FF4D4D] text-white w-4 h-4 rounded-full text-[10px]">×</button>
                  </div>
                ))}
              </div>
            )}
          </label>
          <div className="flex gap-3 pt-2">
            <button data-testid="modal-submit" type="submit" disabled={busy} className="btn-lime flex-1">{busy ? "Sending..." : "Send Request"}</button>
            <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
