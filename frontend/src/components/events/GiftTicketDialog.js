import React, { useState } from "react";
import { Gift, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { api, ORIGIN } from "../../api";

const inputCls = "w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 text-sm outline-none focus:border-[#CCFF00]";

export function GiftTicketDialog({ ev, onClose }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(`/payments/events/${ev.id}/gift`, { origin_url: ORIGIN, recipient_email: email, recipient_name: name, message });
      window.location.href = r.data.checkout_url;
    } catch (er) {
      toast.error(er?.response?.data?.detail || "Couldn't start gift checkout");
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-6" onClick={onClose} data-testid="gift-ticket-dialog">
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="w-full sm:max-w-md bg-[#121214] border border-white/10 rounded-t-sm sm:rounded-sm p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Gift size={12} /> Gift a ticket</div>
            <div className="font-anton text-2xl uppercase mt-2 leading-tight">{ev.title}</div>
            <div className="text-xs text-zinc-500 mt-1">${ev.ticket_price} · they'll get the QR ticket by email, no account needed</div>
          </div>
          <button type="button" data-testid="gift-close-btn" onClick={onClose} className="text-zinc-500 hover:text-white"><X size={18} /></button>
        </div>
        <input data-testid="gift-email-input" required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Friend's email" className={inputCls} />
        <input data-testid="gift-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Friend's name (optional)" maxLength={80} className={inputCls} />
        <textarea data-testid="gift-message-input" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Add a note (optional)" maxLength={400} rows={3} className={inputCls} />
        <button data-testid="gift-pay-btn" type="submit" disabled={busy} className="btn-lime w-full !py-3">
          {busy ? <Loader2 size={14} className="animate-spin inline" /> : `Pay $${ev.ticket_price} & send`}
        </button>
      </form>
    </div>
  );
}
