import React, { useEffect, useState } from "react";
import { Loader2, Megaphone, Mail, MessageSquare, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../api";

const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#CCFF00]";

function Toggle({ id, checked, onChange, icon, label }) {
  return (
    <label className={`flex items-center gap-2 px-3 py-2 rounded-sm border cursor-pointer text-xs transition-colors ${checked ? "border-[#CCFF00]/60 bg-[#CCFF00]/10 text-[#CCFF00]" : "border-white/12 text-zinc-400 hover:border-white/30"}`}>
      <input data-testid={id} type="checkbox" className="hidden" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {icon} {label}
    </label>
  );
}

export function BroadcastModal({ ev, attendeeCount, onClose }) {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [viaDm, setViaDm] = useState(true);
  const [viaEmail, setViaEmail] = useState(true);
  const [includeWaitlist, setIncludeWaitlist] = useState(false);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);

  const loadHistory = () => api.get(`/events/${ev.id}/broadcasts`).then((r) => setHistory(r.data)).catch(() => {});
  useEffect(() => { loadHistory(); }, [ev.id]);

  const send = async (e) => {
    e.preventDefault();
    if (!viaDm && !viaEmail) return toast.error("Pick at least one channel");
    setBusy(true);
    try {
      const r = await api.post(`/events/${ev.id}/broadcast`, { subject, message, via_dm: viaDm, via_email: viaEmail, include_waitlist: includeWaitlist });
      toast.success(`Sent to ${r.data.recipients} people · ${r.data.dm} DMs · ${r.data.email} emails`);
      setSubject(""); setMessage("");
      loadHistory();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed to send"); }
    setBusy(false);
  };

  return (
    <div onClick={onClose} data-testid="broadcast-modal"
      className="fixed inset-0 z-[1200] bg-black/85 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto">
      <div onClick={(e) => e.stopPropagation()} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-xl my-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/8">
          <div className="flex items-center gap-2 font-unbounded font-semibold text-sm">
            <Megaphone size={14} className="text-[#CCFF00]" /> Message attendees
          </div>
          <button data-testid="broadcast-close" onClick={onClose} className="text-zinc-500 hover:text-white"><X size={16} /></button>
        </div>
        <form onSubmit={send} className="p-5 space-y-3">
          <div className="text-xs text-zinc-500">
            Goes to <span className="text-zinc-200">{attendeeCount}</span> confirmed attendee{attendeeCount === 1 ? "" : "s"}{includeWaitlist ? " + everyone on the waitlist" : ""}. Great for weather changes, venue updates, or a thank-you.
          </div>
          <input data-testid="broadcast-subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject — e.g. Venue moved indoors" maxLength={120} className={inputCls} required />
          <textarea data-testid="broadcast-message" value={message} onChange={(e) => setMessage(e.target.value)} rows={5} maxLength={2000}
            placeholder="Your message…" className={inputCls} required />
          <div className="flex flex-wrap gap-2">
            <Toggle id="broadcast-via-dm" checked={viaDm} onChange={setViaDm} icon={<MessageSquare size={12} />} label="Direct message" />
            <Toggle id="broadcast-via-email" checked={viaEmail} onChange={setViaEmail} icon={<Mail size={12} />} label="Email" />
            <Toggle id="broadcast-include-waitlist" checked={includeWaitlist} onChange={setIncludeWaitlist} icon={<Megaphone size={12} />} label="Include waitlist" />
          </div>
          <button data-testid="broadcast-send" type="submit" disabled={busy || !subject.trim() || !message.trim()}
            className="btn-lime w-full !py-3 flex items-center justify-center gap-2 text-xs">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Megaphone size={14} />} Send broadcast
          </button>
        </form>
        {history.length > 0 && (
          <div className="border-t border-white/8 px-5 py-4" data-testid="broadcast-history">
            <div className="label-caps text-zinc-500 mb-2">Sent</div>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {history.map((b) => (
                <div key={b.id} className="text-xs border border-white/8 rounded-sm p-2.5">
                  <div className="flex justify-between gap-2">
                    <span className="text-zinc-200 font-semibold truncate">{b.subject}</span>
                    <span className="text-zinc-500 flex-shrink-0">{new Date(b.created_at).toLocaleString()}</span>
                  </div>
                  <div className="text-zinc-500 mt-1">{b.recipients} people · {b.dm} DM · {b.email} email</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
