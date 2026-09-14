import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { Radar, RefreshCw, MapPin } from "lucide-react";

const STATUS_META = {
  pre_transit: { label: "Label created", color: "#71717A" },
  in_transit: { label: "In transit", color: "#7C3AED" },
  out_for_delivery: { label: "Out for delivery", color: "#F5A623" },
  delivered: { label: "Delivered", color: "#CCFF00" },
  available_for_pickup: { label: "Available for pickup", color: "#F5A623" },
  return_to_sender: { label: "Returned to sender", color: "#FF4D4D" },
  failure: { label: "Delivery failed", color: "#FF4D4D" },
  unknown: { label: "Awaiting carrier scan", color: "#71717A" },
};

export function LiveTrackingPanel({ orderId, fulfillment }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try { const r = await api.get(`/orders/${orderId}/tracking`); setData(r.data); } catch {}
    setBusy(false);
  };
  useEffect(() => { if (fulfillment?.tracking) load(); }, [orderId, fulfillment?.tracking, fulfillment?.status]);

  if (!fulfillment?.tracking || !data) return null;
  const live = data.live_tracking && data.tracker_id;
  const meta = STATUS_META[data.tracking_status] || STATUS_META.unknown;

  return (
    <div className="mt-4 pt-4 border-t border-white/8" data-testid="live-tracking-panel">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="label-caps flex items-center gap-2">
          <Radar size={12} className={live ? "text-[#CCFF00]" : "text-zinc-500"} />
          {live ? "Live carrier tracking" : "Manual tracking"}
          {live && <span className="px-2 py-0.5 rounded-sm text-[10px]" style={{ background: `${meta.color}20`, color: meta.color }} data-testid="tracking-status-chip">{meta.label}</span>}
        </div>
        {live && (
          <button onClick={load} disabled={busy} className="text-[11px] text-zinc-400 hover:text-[#CCFF00] inline-flex items-center gap-1" data-testid="tracking-refresh-btn">
            <RefreshCw size={11} className={busy ? "animate-spin" : ""} /> Refresh
          </button>
        )}
      </div>
      {live ? (
        <>
          {data.est_delivery && <div className="text-xs text-zinc-400 mt-2">Estimated delivery {new Date(data.est_delivery).toLocaleDateString()}</div>}
          {data.tracking_events?.length > 0 && (
            <ol className="mt-3 space-y-2" data-testid="tracking-events">
              {[...data.tracking_events].reverse().map((ev, i) => (
                <li key={i} className="flex gap-3 text-xs">
                  <span className="mt-1 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: i === 0 ? meta.color : "#3f3f46" }} />
                  <div className="min-w-0">
                    <div className="text-zinc-200">{ev.message || ev.status}</div>
                    <div className="text-zinc-500 flex items-center gap-1">
                      {(ev.city || ev.state) && <><MapPin size={10} /> {[ev.city, ev.state].filter(Boolean).join(", ")} · </>}
                      {ev.at ? new Date(ev.at).toLocaleString() : ""}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
          {data.tracking_url && <a href={data.tracking_url} target="_blank" rel="noreferrer" className="text-[11px] text-[#7C3AED] hover:underline mt-2 inline-block">Open carrier tracking page →</a>}
          <div className="text-[11px] text-zinc-500 mt-2">When the carrier reports delivered, the collector is prompted to confirm automatically.</div>
        </>
      ) : (
        <div className="text-[11px] text-zinc-500 mt-2" data-testid="manual-tracking-note">Live tracking isn't connected yet — the seller confirms delivery manually, or it's estimated 7 days after shipping.</div>
      )}
    </div>
  );
}
