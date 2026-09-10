import React, { useState } from "react";
import { CalendarPlus, Copy, X, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, copyText } from "../api";

export function CalendarSubscribe() {
  const [info, setInfo] = useState(null);
  const [open, setOpen] = useState(false);
  const load = async () => { const r = await api.post("/calendar/token"); setInfo(r.data); };
  const openIt = async () => { setOpen(true); if (!info) try { await load(); } catch { toast.error("Couldn't create calendar link"); } };
  const copy = (t) => { copyText(t); toast.success("Copied"); };
  const reset = async () => { await api.delete("/calendar/token"); setInfo(null); await load(); toast.success("New private link generated"); };
  return (
    <>
      <button data-testid="calendar-subscribe-btn" onClick={openIt} className="btn-ghost !py-2 !px-3 text-xs flex items-center gap-2"><CalendarPlus size={13} /> Sync to calendar</button>
      {open && (
        <div onClick={() => setOpen(false)} data-testid="calendar-modal" className="fixed inset-0 z-[1300] bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div onClick={(e) => e.stopPropagation()} className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-lg p-5 space-y-4">
            <div className="flex items-center justify-between"><div className="font-unbounded font-semibold text-sm flex items-center gap-2"><CalendarPlus size={13} className="text-[#CCFF00]" /> Live calendar feed</div><button onClick={() => setOpen(false)} className="text-zinc-500"><X size={15} /></button></div>
            <p className="text-xs text-zinc-400">Every event you RSVP to or save shows up automatically in Google Calendar, Apple Calendar or Outlook — with a 24h reminder. Updates every few hours.</p>
            {!info ? <div className="text-xs text-zinc-500">Generating your private link…</div> : (
              <>
                <a data-testid="calendar-google" href={info.google_url} target="_blank" rel="noreferrer" className="btn-lime w-full !py-2.5 text-xs flex items-center justify-center gap-2">Add to Google Calendar</a>
                <a data-testid="calendar-apple" href={info.webcal_url} className="btn-ghost w-full !py-2.5 text-xs flex items-center justify-center gap-2">Add to Apple / Outlook (webcal)</a>
                <div className="flex items-center gap-2">
                  <input data-testid="calendar-url" readOnly value={info.url} className="flex-1 min-w-0 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 text-[11px] text-zinc-300 outline-none" />
                  <button data-testid="calendar-copy" onClick={() => copy(info.url)} className="btn-ghost !py-2 !px-3"><Copy size={12} /></button>
                </div>
                <button data-testid="calendar-reset" onClick={reset} className="text-[11px] text-zinc-500 hover:text-[#FF4D4D] flex items-center gap-1"><RefreshCw size={10} /> This link is private — regenerate it if it leaks</button>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
