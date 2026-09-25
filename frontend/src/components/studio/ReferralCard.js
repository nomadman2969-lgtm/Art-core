import React, { useEffect, useState } from "react";
import { api, copyText } from "../../api";
import { toast } from "sonner";
import { Users, Copy, Share2, Gift, Check } from "lucide-react";

export function ReferralCard() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/referrals/me").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return null;

  const share = async () => {
    const text = "I sell my art on Art Core — 0% fees your first 30 days, then a locked low rate. Join with my link:";
    if (navigator.share) { try { await navigator.share({ title: "Join me on Art Core", text, url: d.link }); return; } catch {} }
    copyText(d.link); toast.success("Invite link copied");
  };

  return (
    <div className="glass-card rounded-sm p-6 border border-[#CCFF00]/25" data-testid="referral-card">
      <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Users size={12} /> Invite artists</div>
      <div className="font-anton text-2xl md:text-3xl uppercase mt-2">Bring a fellow artist. Your next sale is fee-free.</div>
      <p className="text-sm text-zinc-400 mt-2 leading-relaxed">When someone joins with your link and makes their first sale, Art Core takes <span className="text-white">0%</span> on your next sale — and you both earn a badge. They get the same 30-day 0% start everyone gets.</p>
      <div className="flex flex-col sm:flex-row gap-2 mt-4">
        <div className="flex-1 font-mono text-xs bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2.5 truncate" data-testid="referral-link">{d.link}</div>
        <button onClick={() => { copyText(d.link); toast.success("Copied"); }} className="btn-ghost !py-2 !text-xs inline-flex items-center gap-2" data-testid="referral-copy"><Copy size={12} /> Copy</button>
        <button onClick={share} className="btn-lime !py-2 !text-xs inline-flex items-center gap-2" data-testid="referral-share"><Share2 size={12} /> Share</button>
      </div>
      <div className="grid grid-cols-3 gap-3 mt-5">
        {[["Invited", d.invited, "referral-invited"], ["Made a sale", d.converted, "referral-converted"], ["Fee-free sales ready", d.fee_free_sales, "referral-credits"]].map(([l, v, id]) => (
          <div key={l} className="border border-white/8 rounded-sm p-3">
            <div className="font-anton text-2xl text-[#CCFF00]" data-testid={id}>{v}</div>
            <div className="label-caps text-[10px] text-zinc-500 mt-1">{l}</div>
          </div>
        ))}
      </div>
      {d.fee_free_sales > 0 && <div className="text-xs text-[#CCFF00] mt-3 flex items-center gap-2" data-testid="referral-credit-note"><Gift size={12} /> Your next {d.fee_free_sales === 1 ? "sale" : `${d.fee_free_sales} sales`} will be charged 0% commission automatically.</div>}
      {d.invitees.length > 0 && (
        <ul className="mt-4 space-y-1.5" data-testid="referral-invitees">
          {d.invitees.slice(0, 8).map((i) => (
            <li key={i.id} className="flex items-center justify-between text-xs">
              <span className="text-zinc-300">{i.name}</span>
              <span className={`flex items-center gap-1 ${i.first_sale_at ? "text-[#CCFF00]" : "text-zinc-500"}`}>{i.first_sale_at ? <><Check size={11} /> first sale</> : "joined · no sale yet"}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
