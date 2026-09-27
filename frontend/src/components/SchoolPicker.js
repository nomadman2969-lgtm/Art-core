import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { GraduationCap, X, Plus, Loader2 } from "lucide-react";

// Searchable school combobox. value: {id,name,city} | null. onChange(campus | {name} | null)
export function SchoolPicker({ value, onChange, allowCreate = true, placeholder = "Search your school…", testid = "school-picker", disabled = false }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    setBusy(true);
    const t = setTimeout(() => {
      api.get("/campus/search", { params: { q: q.trim() } }).then((r) => setResults(r.data)).catch(() => setResults([])).finally(() => setBusy(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const onDoc = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (value) {
    return (
      <div data-testid={`${testid}-selected`} className="flex items-center gap-3 bg-white/[0.03] border border-[#CCFF00]/40 rounded-sm px-3 py-2.5">
        <GraduationCap size={16} className="text-[#CCFF00] shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="font-unbounded text-sm truncate">{value.name}</div>
          {value.city && <div className="text-[11px] text-zinc-500 truncate">{value.city}{value.country ? ` · ${value.country}` : ""}{value.status === "pending" ? " · awaiting approval" : ""}</div>}
        </div>
        {!disabled && <button type="button" data-testid={`${testid}-clear`} onClick={() => onChange(null)} className="text-zinc-500 hover:text-[#FF4D4D]"><X size={14} /></button>}
      </div>
    );
  }

  const exact = results.some((r) => r.name.toLowerCase() === q.trim().toLowerCase());
  const showCreate = allowCreate && q.trim().length >= 3 && !exact && !busy;
  return (
    <div ref={box} className="relative">
      <div className="flex items-center gap-2 bg-white/[0.03] border border-white/12 rounded-sm px-3 focus-within:border-[#CCFF00]">
        <GraduationCap size={16} className="text-zinc-500 shrink-0" />
        <input data-testid={`${testid}-input`} value={q} disabled={disabled} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          placeholder={placeholder} className="flex-1 bg-transparent py-2.5 outline-none text-sm" autoComplete="off" />
        {busy && <Loader2 size={14} className="animate-spin text-zinc-500" />}
      </div>
      {open && q.trim().length >= 2 && (
        <div data-testid={`${testid}-results`} className="absolute z-40 left-0 right-0 mt-1 bg-[#121214] border border-white/12 rounded-sm shadow-2xl max-h-72 overflow-y-auto">
          {results.map((r) => (
            <button type="button" key={r.id} data-testid={`${testid}-option-${r.id}`} onClick={() => { onChange(r); setQ(""); setOpen(false); }}
              className="w-full text-left px-3 py-2.5 hover:bg-white/[0.05] border-b border-white/5 last:border-0">
              <div className="text-sm">{r.name}{r.aliases?.length ? <span className="text-zinc-500"> · {r.aliases.join(", ")}</span> : null}</div>
              <div className="text-[11px] text-zinc-500">{[r.city, r.country].filter(Boolean).join(" · ")}{r.status === "pending" ? " · pending" : ""}</div>
            </button>
          ))}
          {results.length === 0 && !busy && !showCreate && <div className="px-3 py-3 text-xs text-zinc-500">No matches yet — keep typing.</div>}
          {showCreate && (
            <button type="button" data-testid={`${testid}-create`} onClick={() => { onChange({ name: q.trim(), isNew: true }); setQ(""); setOpen(false); }}
              className="w-full text-left px-3 py-2.5 hover:bg-[#CCFF00]/10 text-[#CCFF00] text-sm flex items-center gap-2">
              <Plus size={14} /> Add “{q.trim()}” as my school
            </button>
          )}
        </div>
      )}
    </div>
  );
}
