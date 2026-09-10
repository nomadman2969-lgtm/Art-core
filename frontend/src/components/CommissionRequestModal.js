import React, { useState } from "react";
import { api, fileUrl } from "../api";
import { toast } from "sonner";
import { X, Upload, Palette, Hammer } from "lucide-react";

const FURNITURE = [["chair","Chair"],["table","Table"],["dresser","Dresser"],["cabinet","Cabinet"],["desk","Desk"],["shelf","Shelf"],["lamp","Lamp"],["bench","Bench"],["mirror","Mirror / Frame"],["other","Other"]];
const HANDOFF = [["dropoff","I'll drop it off"],["pickup","Artist picks it up"],["ship","I'll ship it"]];
const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]";

/**
 * Modal for collectors to submit a commission request from an artist's Studio.
 * Uses existing POST /api/commissions endpoint. Fields: subject, description,
 * budget, deadline, reference_images (upload). Notifies artist via existing
 * commission_request notification wiring.
 */
export default function CommissionRequestModal({ artist, onClose, onSubmitted, mode = "art", allowFlip = false }) {
  const [kind, setKind] = useState(mode);
  const [form, setForm] = useState({ subject: "", instructions: "", budget: mode === "flip" ? 350 : 500, deadline: "" });
  const [furn, setFurn] = useState({ furniture_type: "chair", dimensions: "", condition: "good", handoff: "dropoff", city: "" });
  const isFlip = kind === "flip";
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
    if (isFlip && refs.length === 0) { toast.error("Add at least one photo of your furniture"); return; }
    setBusy(true);
    try {
      const r = await api.post("/commissions", {
        artist_id: artist.id,
        subject: form.subject,
        instructions: form.instructions,
        budget: Number(form.budget),
        deadline: form.deadline || null,
        reference_images: refs,
        kind,
        furniture: isFlip ? { ...furn, city: furn.city || null, dimensions: furn.dimensions || null } : null,
      });
      toast.success(isFlip ? `Flip request sent to ${artist.name}` : `Request sent to ${artist.name}`);
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
            <div className="label-caps text-[#CCFF00]">{isFlip ? <Hammer size={12} className="inline mr-2" /> : <Palette size={12} className="inline mr-2" />} {isFlip ? "Furniture flip" : "Commission"}</div>
            <div className="font-anton text-2xl uppercase mt-1">{isFlip ? `Have ${artist.name} flip it` : `Request from ${artist.name}`}</div>
          </div>
          <button data-testid="modal-close" onClick={onClose} className="text-zinc-500 hover:text-white p-1"><X size={18} /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          {(allowFlip || mode === "flip") && (
            <div className="grid grid-cols-2 gap-2" data-testid="commission-kind-toggle">
              {[["art", "Original artwork", Palette], ["flip", "Flip my furniture", Hammer]].map(([k, l, Icon]) => (
                <button key={k} type="button" data-testid={`commission-kind-${k}`} onClick={() => setKind(k)}
                  className={`label-caps text-[10px] py-2.5 rounded-sm border flex items-center justify-center gap-2 transition-colors ${kind === k ? "border-[#CCFF00] text-[#CCFF00] bg-[#CCFF00]/10" : "border-white/12 text-zinc-400 hover:border-white/30"}`}>
                  <Icon size={12} /> {l}
                </button>
              ))}
            </div>
          )}
          {isFlip && (
            <div className="border border-[#34D399]/30 bg-[#34D399]/5 rounded-sm p-4 space-y-3" data-testid="flip-fields">
              <div className="text-xs text-zinc-400">You keep ownership of the piece. Payment sits in escrow — a deposit to start, the balance released only when you approve the finished flip.</div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block"><div className="label-caps mb-2">Furniture type</div>
                  <select data-testid="flip-type" value={furn.furniture_type} onChange={(e) => setFurn({ ...furn, furniture_type: e.target.value })} className={inputCls + " bg-[#0A0A0C]"}>
                    {FURNITURE.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select></label>
                <label className="block"><div className="label-caps mb-2">Condition</div>
                  <select data-testid="flip-condition" value={furn.condition} onChange={(e) => setFurn({ ...furn, condition: e.target.value })} className={inputCls + " bg-[#0A0A0C]"}>
                    {[["good", "Good — solid"], ["worn", "Worn — needs love"], ["damaged", "Damaged — needs repair"]].map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select></label>
              </div>
              <label className="block"><div className="label-caps mb-2">Dimensions (optional)</div>
                <input data-testid="flip-dimensions" value={furn.dimensions} onChange={(e) => setFurn({ ...furn, dimensions: e.target.value })} placeholder={"e.g. 36\" W × 18\" D × 32\" H"} className={inputCls} /></label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block"><div className="label-caps mb-2">Hand-off</div>
                  <select data-testid="flip-handoff" value={furn.handoff} onChange={(e) => setFurn({ ...furn, handoff: e.target.value })} className={inputCls + " bg-[#0A0A0C]"}>
                    {HANDOFF.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select></label>
                <label className="block"><div className="label-caps mb-2">Your city</div>
                  <input data-testid="flip-city" value={furn.city} onChange={(e) => setFurn({ ...furn, city: e.target.value })} placeholder="Austin, TX" className={inputCls} /></label>
              </div>
            </div>
          )}
          <label className="block">
            <div className="label-caps mb-2">{isFlip ? "What should it become?" : "Project subject"}</div>
            <input data-testid="modal-subject" required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
              placeholder={isFlip ? "Grandma's dresser → neon graffiti statement piece" : "Portrait of my dog on a purple background"}
              className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 outline-none focus:border-[#CCFF00]" />
          </label>
          <label className="block">
            <div className="label-caps mb-2">Description</div>
            <textarea data-testid="modal-description" required rows={4} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })}
              placeholder={isFlip ? "Colors, vibe, rooms it lives in, anything to keep or protect (hardware, drawers)..." : "Style, size preferences, color palette, anything you want them to know..."}
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
            <div className="label-caps mb-2">{isFlip ? "Photos of your furniture (required)" : "Reference images (optional)"}</div>
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
            <button data-testid="modal-submit" type="submit" disabled={busy} className="btn-lime flex-1">{busy ? "Sending..." : isFlip ? "Send Flip Request" : "Send Request"}</button>
            <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
