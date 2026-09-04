import React, { useState, useRef, useEffect } from "react";
import { api } from "../api";

/**
 * MentionInput — textarea/input with @-autocomplete.
 * Detects the token at the caret starting with '@', queries /users/search,
 * and lets the user pick with arrow keys + enter.
 *
 * Props: value, onChange, placeholder, rows (0 = input, >0 = textarea), disabled, testId, className
 */
export default function MentionInput({ value, onChange, placeholder, rows = 0, disabled, testId, className, autoFocus }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const [tokenStart, setTokenStart] = useState(null);
  const ref = useRef(null);

  const scanToken = (v, caret) => {
    // Walk left from caret to find an @ token boundary
    let i = caret - 1;
    while (i >= 0 && /[a-zA-Z0-9_\-.]/.test(v[i])) i--;
    if (i < 0 || v[i] !== "@") return null;
    // Boundary before '@' must be start-of-string or whitespace
    if (i > 0 && !/\s/.test(v[i - 1])) return null;
    return { start: i, query: v.slice(i + 1, caret) };
  };

  const onInput = (e) => {
    const v = e.target.value;
    onChange(v);
    const caret = e.target.selectionStart;
    const tok = scanToken(v, caret);
    if (tok && tok.query.length >= 0 && tok.query.length <= 32) {
      setTokenStart(tok.start);
      // Fetch suggestions
      api.get(`/users/search?q=${encodeURIComponent(tok.query || "a")}&limit=6`).then((r) => {
        setSuggestions(r.data);
        setOpen(r.data.length > 0);
        setActiveIdx(0);
      }).catch(() => { setSuggestions([]); setOpen(false); });
    } else {
      setOpen(false);
      setSuggestions([]);
      setTokenStart(null);
    }
  };

  const insertMention = (u) => {
    if (tokenStart == null || !ref.current) return;
    const el = ref.current;
    const caret = el.selectionStart;
    const before = value.slice(0, tokenStart);
    const after = value.slice(caret);
    const handle = (u.name || "").replace(/\s+/g, "");
    const insert = `@${handle} `;
    const next = before + insert + after;
    onChange(next);
    setOpen(false);
    setSuggestions([]);
    setTokenStart(null);
    // Restore caret
    setTimeout(() => {
      const p = before.length + insert.length;
      el.focus();
      el.setSelectionRange(p, p);
    }, 0);
  };

  const onKeyDown = (e) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => (i + 1) % suggestions.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx((i) => (i - 1 + suggestions.length) % suggestions.length); }
    else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); insertMention(suggestions[activeIdx]); }
    else if (e.key === "Escape") { setOpen(false); }
  };

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const Comp = rows > 0 ? "textarea" : "input";
  return (
    <div className="relative w-full">
      <Comp
        ref={ref}
        data-testid={testId}
        value={value}
        onChange={onInput}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows > 0 ? rows : undefined}
        autoFocus={autoFocus}
        className={className}
      />
      {open && suggestions.length > 0 && (
        <div data-testid={`${testId}-suggestions`} className="absolute z-40 left-0 top-full mt-1 bg-[#121214] border border-white/12 rounded-sm shadow-xl min-w-[240px] max-h-64 overflow-y-auto">
          {suggestions.map((u, i) => (
            <button
              key={u.id}
              type="button"
              data-testid={`mention-item-${u.id}`}
              onMouseDown={(e) => { e.preventDefault(); insertMention(u); }}
              className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${i === activeIdx ? "bg-[#CCFF00]/15" : "hover:bg-white/[0.05]"}`}
            >
              <div className="w-8 h-8 rounded-full flex items-center justify-center font-anton text-sm flex-shrink-0"
                style={{ background: u.role === "artist" ? "#CCFF0040" : "#7C3AED40", color: u.role === "artist" ? "#CCFF00" : "#7C3AED" }}>
                {u.name?.[0]?.toUpperCase() || "?"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-unbounded font-semibold truncate">{u.name}</div>
                <div className="text-xs text-zinc-500 truncate">
                  {u.role === "artist" ? "Artist" : u.role === "admin" ? "Admin" : "Collector"}
                  {u.bio ? ` · ${u.bio}` : ""}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
