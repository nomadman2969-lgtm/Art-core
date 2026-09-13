import React, { useState } from "react";
import { Wallet, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, API } from "../../api";

// Downloads a lock-screen-ready ticket card. Native Apple/Google Wallet passes need signing credentials — this is the credential-free path.
export function WalletPassButton({ eventId, giftToken, className = "" }) {
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      let blob;
      if (giftToken) {
        const r = await fetch(`${API}/events/gift/${giftToken}/pass.png`);
        if (!r.ok) throw new Error();
        blob = await r.blob();
      } else {
        const r = await api.get(`/events/${eventId}/my-ticket/pass.png`, { responseType: "blob" });
        blob = r.data;
      }
      const file = new File([blob], "artcore-ticket.png", { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: "Art Core ticket" });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = "artcore-ticket.png"; a.click();
        URL.revokeObjectURL(url);
        toast.success("Ticket saved — add it to Photos or your lock screen");
      }
    } catch (e) { if (e?.name !== "AbortError") toast.error("Couldn't build the pass"); }
    finally { setBusy(false); }
  };
  return (
    <button data-testid="wallet-pass-btn" onClick={save} disabled={busy}
      className={`btn-ghost flex items-center justify-center gap-2 text-xs ${className}`}>
      {busy ? <Loader2 size={14} className="animate-spin" /> : <Wallet size={14} />} Add to Wallet
    </button>
  );
}
