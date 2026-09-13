import { useTranslation } from "react-i18next";
import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Search, Send, Paperclip, Image as ImageIcon, Palette, Check, CheckCheck, X, Smile } from "lucide-react";
import { useLive } from "../hooks/useLive";

const REACTION_EMOJIS = [
  { key: "heart", char: "❤️" },
  { key: "fire", char: "🔥" },
  { key: "mind_blown", char: "🤯" },
  { key: "wow", char: "😮" },
  { key: "clap", char: "👏" },
  { key: "eye", char: "👀" },
];
const emojiChar = (key) => REACTION_EMOJIS.find((e) => e.key === key)?.char || key;

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const diffDays = (now - d) / (1000 * 60 * 60 * 24);
  if (diffDays < 7) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function MessagesInbox() {
  const { t } = useTranslation();
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const load = (query = "") => {
    setLoading(true);
    api.get(`/messages/threads${query ? `?q=${encodeURIComponent(query)}` : ""}`)
      .then((r) => setThreads(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const t = setTimeout(() => load(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div data-testid="messages-inbox" className="max-w-3xl mx-auto px-4 md:px-6 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">{t("messages.kicker")}</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-3">{t("messages.title")}</h1>
      <div className="relative mt-8 mb-6">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
        <input data-testid="messages-search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={t("messages.search")}
          className="w-full bg-white/[0.03] border border-white/12 rounded-sm pl-9 pr-3 py-3 outline-none focus:border-[#CCFF00]" />
      </div>
      {loading && threads.length === 0 ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        threads.length === 0 ? (
          <div className="border border-dashed border-white/10 py-16 text-center rounded-sm">
            <div className="label-caps text-zinc-500">{q ? t("messages.no_matches") : t("messages.empty")}</div>
            {!q && <div className="text-sm text-zinc-400 mt-4">Message an artist from their Studio to start.</div>}
          </div>
        ) : (
          <div className="divide-y divide-white/8 border border-white/8 rounded-sm">
            {threads.map((t) => (
              <Link key={t.thread_key} to={`/messages/${t.other_user_id}`} data-testid={`thread-${t.other_user_id}`}
                className="flex items-center gap-3 p-4 hover:bg-white/[0.03] transition-colors">
                <div className="w-12 h-12 rounded-full bg-[#7C3AED]/20 flex items-center justify-center font-anton text-xl flex-shrink-0">
                  {t.other_user_name[0]?.toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className={`font-unbounded truncate ${t.unread > 0 ? "font-bold" : "font-semibold"}`}>{t.other_user_name}</div>
                    <div className="text-xs text-zinc-500 flex-shrink-0">{fmtTime(t.last_at)}</div>
                  </div>
                  <div className={`text-sm truncate mt-1 flex items-center gap-1 ${t.unread > 0 ? "text-white" : "text-zinc-400"}`}>
                    {t.last_from_me && (t.last_read ? <CheckCheck size={12} className="text-[#CCFF00] flex-shrink-0" /> : <Check size={12} className="text-zinc-500 flex-shrink-0" />)}
                    {t.last_from_me && <span className="text-zinc-500">You: </span>}
                    <span className="truncate">{t.last_message || "…"}</span>
                  </div>
                </div>
                {t.unread > 0 && <div data-testid={`unread-${t.other_user_id}`} className="min-w-[22px] h-[22px] px-1.5 rounded-full bg-[#CCFF00] text-black text-xs font-bold flex items-center justify-center flex-shrink-0">{t.unread}</div>}
              </Link>
            ))}
          </div>
        )}
    </div>
  );
}

export function MessageThread() {
  const { t } = useTranslation();
  const { userId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [reactingTo, setReactingTo] = useState(null);
  const endRef = useRef(null);
  const fileRef = useRef(null);
  const lastTypeRef = useRef(0);

  const load = () => api.get(`/messages/thread/${userId}`).then((r) => setData(r.data));
  const liveConnected = useLive([], (ev) => { if ((ev.type === "dm" || ev.type === "typing") && (ev.from_id === userId || ev.to_id === userId)) load(); });
  useEffect(() => { load(); const t = setInterval(load, liveConnected ? 15000 : 3000); return () => clearInterval(t); }, [userId, liveConnected]);
  useEffect(() => {
    const el = endRef.current?.parentElement;
    if (el) el.scrollTop = el.scrollHeight;
  }, [data?.messages?.length, data?.other_typing]);

  const onTextChange = (v) => {
    setText(v);
    const now = Date.now();
    if (v && now - lastTypeRef.current > 2500) {
      lastTypeRef.current = now;
      api.post(`/messages/thread/${userId}/typing`).catch(() => {});
    }
  };

  const react = async (messageId, emoji) => {
    try {
      const r = await api.post(`/messages/${messageId}/react`, { emoji });
      setData((d) => ({ ...d, messages: d.messages.map((m) => m.id === messageId ? { ...m, reactions: r.data.reactions } : m) }));
      setReactingTo(null);
    } catch { toast.error("Failed"); }
  };

  const uploadImg = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/upload/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setAttachment({ kind: "image", url: r.data.url, label: f.name });
    } catch { toast.error("Upload failed"); }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };
  const attachStudio = () => setAttachment({ kind: "studio", ref_id: userId, label: "Studio" });
  const send = async (e) => {
    e.preventDefault();
    if (!text.trim() && !attachment) return;
    setSending(true);
    try {
      await api.post("/messages", { to_user_id: userId, text: text.trim(), attachment });
      setText(""); setAttachment(null); await load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setSending(false);
  };
  if (!data) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  return (
    <div data-testid="message-thread" className="max-w-3xl mx-auto px-3 md:px-6 pt-3 md:pt-16 pb-6 md:pb-32">
      <button onClick={() => nav("/messages")} className="label-caps text-zinc-500 hover:text-[#CCFF00] mb-3">← Inbox</button>
      <div className="border border-white/8 rounded-sm flex flex-col h-[calc(100dvh-140px)] md:h-[70vh]">
        <div className="p-4 border-b border-white/8 flex items-center gap-3 flex-shrink-0">
          <Link to={`/artist/${data.other?.id}`} className="w-11 h-11 rounded-full bg-[#CCFF00]/20 flex items-center justify-center font-anton flex-shrink-0">
            {data.other?.name?.[0]?.toUpperCase() || "?"}
          </Link>
          <div className="flex-1 min-w-0">
            <Link to={`/artist/${data.other?.id}`} className="font-unbounded font-semibold hover:text-[#CCFF00]">{data.other?.name}</Link>
            <div className="label-caps mt-0.5 text-zinc-500">{data.other?.role}</div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-[#0A0A0C]">
          {data.messages.length === 0 && <div className="text-zinc-500 label-caps text-center py-16">Say hi.</div>}
          {data.messages.map((m, i) => {
            const mine = m.from_id === user.id;
            const prev = data.messages[i - 1];
            const showTime = !prev || (new Date(m.created_at) - new Date(prev.created_at)) > 5 * 60 * 1000;
            const grouped = (m.reactions || []).reduce((acc, r) => {
              acc[r.emoji] = acc[r.emoji] || { count: 0, mine: false };
              acc[r.emoji].count += 1;
              if (r.user_id === user.id) acc[r.emoji].mine = true;
              return acc;
            }, {});
            const showPicker = reactingTo === m.id;
            return (
              <div key={m.id} data-testid={`msg-${m.id}`}>
                {showTime && <div className="text-center text-xs text-zinc-600 label-caps my-3">{new Date(m.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</div>}
                <div className={`group flex items-end gap-1 ${mine ? "justify-end" : "justify-start"}`}>
                  {mine && (
                    <button
                      data-testid={`react-btn-${m.id}`}
                      onClick={() => setReactingTo(showPicker ? null : m.id)}
                      className="opacity-40 md:opacity-0 md:group-hover:opacity-100 text-zinc-500 hover:text-[#CCFF00] transition-opacity p-1"
                      aria-label="React">
                      <Smile size={14} />
                    </button>
                  )}
                  <div className={`max-w-[80%] rounded-sm ${mine ? "bg-[#CCFF00] text-black" : "bg-[#1A1A1E] text-white"} overflow-hidden relative`}>
                    {m.attachment && <AttachmentCard att={m.attachment} mine={mine} />}
                    {m.text && <div className={`px-3 py-2 text-sm whitespace-pre-wrap ${m.attachment ? "border-t border-black/10" : ""}`}>{m.text}</div>}
                    {mine && (
                      <div className="px-3 pb-1 text-[10px] opacity-60 flex items-center justify-end gap-1">
                        {m.read ? <CheckCheck size={10} /> : <Check size={10} />}
                        <span>{fmtTime(m.created_at)}</span>
                      </div>
                    )}
                    {Object.keys(grouped).length > 0 && (
                      <div data-testid={`reactions-${m.id}`} className="flex gap-1 px-2 pb-2 flex-wrap">
                        {Object.entries(grouped).map(([emoji, info]) => (
                          <button
                            key={emoji}
                            onClick={() => react(m.id, emoji)}
                            data-testid={`reaction-chip-${m.id}-${emoji}`}
                            className={`text-[11px] px-1.5 py-0.5 rounded-full border ${info.mine ? "border-[#CCFF00] bg-[#CCFF00]/20 text-white" : "border-white/20 bg-black/30 text-white/80"}`}>
                            {emojiChar(emoji)} {info.count}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  {!mine && (
                    <button
                      data-testid={`react-btn-${m.id}`}
                      onClick={() => setReactingTo(showPicker ? null : m.id)}
                      className="opacity-40 md:opacity-0 md:group-hover:opacity-100 text-zinc-500 hover:text-[#CCFF00] transition-opacity p-1"
                      aria-label="React">
                      <Smile size={14} />
                    </button>
                  )}
                </div>
                {showPicker && (
                  <div data-testid={`reaction-picker-${m.id}`} className={`flex ${mine ? "justify-end" : "justify-start"} mt-1`}>
                    <div className="inline-flex items-center gap-1 bg-[#121214] border border-white/10 rounded-full px-2 py-1 shadow-lg">
                      {REACTION_EMOJIS.map((e) => (
                        <button
                          key={e.key}
                          data-testid={`pick-${m.id}-${e.key}`}
                          onClick={() => react(m.id, e.key)}
                          className="text-lg hover:scale-125 transition-transform px-1">
                          {e.char}
                        </button>
                      ))}
                      <button onClick={() => setReactingTo(null)} className="text-zinc-500 hover:text-white px-1"><X size={12} /></button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          {data.other_typing && (
            <div data-testid="typing-indicator" className="flex justify-start">
              <div className="bg-[#1A1A1E] text-white rounded-sm px-3 py-2 flex items-center gap-1">
                <span className="text-xs text-zinc-400">{data.other?.name?.split(" ")[0] || "typing"}</span>
                <span className="typing-dots inline-flex gap-0.5 items-end">
                  <span className="w-1 h-1 rounded-full bg-[#CCFF00] animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1 h-1 rounded-full bg-[#CCFF00] animate-bounce" style={{ animationDelay: "120ms" }} />
                  <span className="w-1 h-1 rounded-full bg-[#CCFF00] animate-bounce" style={{ animationDelay: "240ms" }} />
                </span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
        {attachment && (
          <div className="px-4 py-2 border-t border-white/8 flex items-center gap-2 flex-shrink-0" data-testid="pending-attachment">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-sm bg-white/[0.05] flex-1">
              {attachment.kind === "image" && <ImageIcon size={14} className="text-[#CCFF00]" />}
              {attachment.kind === "studio" && <Palette size={14} className="text-[#7C3AED]" />}
              <span className="text-xs">{attachment.label || attachment.kind}</span>
            </div>
            <button onClick={() => setAttachment(null)} className="text-zinc-500 hover:text-[#FF4D4D]"><X size={14} /></button>
          </div>
        )}
        <form onSubmit={send} className="p-3 border-t border-white/8 flex gap-2 flex-shrink-0">
          <label className="btn-ghost !py-2 !px-3 cursor-pointer flex-shrink-0" title="Attach image">
            <Paperclip size={14} />
            <input ref={fileRef} data-testid="attach-image" type="file" accept="image/*" onChange={uploadImg} className="hidden" />
          </label>
          <button type="button" onClick={attachStudio} data-testid="attach-studio" className="btn-ghost !py-2 !px-3 flex-shrink-0" title="Share this studio">
            <Palette size={14} />
          </button>
          <input data-testid="message-input" value={text} onChange={(e) => onTextChange(e.target.value)}
            placeholder={uploading ? t("messages.uploading") : t("messages.type")} disabled={uploading || sending}
            className="flex-1 bg-transparent border border-white/12 px-3 py-2 text-sm outline-none focus:border-[#CCFF00] rounded-sm" />
          <button data-testid="message-send" disabled={sending || uploading || (!text.trim() && !attachment)} className="btn-lime !py-2 !px-3"><Send size={14} /></button>
        </form>
      </div>
    </div>
  );
}

function AttachmentCard({ att, mine }) {
  const textClr = mine ? "text-black" : "text-white";
  if (att.kind === "image") {
    return <img src={att.url?.startsWith("http") ? att.url : fileUrl(att.url?.replace(/^\/api\/files\//, ""))} className="max-w-full max-h-72 object-cover" alt="" />;
  }
  if (att.kind === "artwork") {
    return (
      <Link to={`/artwork/${att.ref_id}`} className={`flex items-center gap-3 p-2 ${textClr}`}>
        {att.image && <img src={resolveImg(att.image)} className="w-14 h-14 object-cover rounded-sm" alt="" />}
        <div className="min-w-0">
          <div className="text-xs opacity-70">Artwork</div>
          <div className="font-unbounded text-sm font-semibold truncate">{att.title}</div>
          <div className="text-xs opacity-70">${Number(att.price || 0).toLocaleString()} · {att.artist_name}</div>
        </div>
      </Link>
    );
  }
  if (att.kind === "studio") {
    return (
      <Link to={`/artist/${att.ref_id}`} className={`flex items-center gap-3 p-3 ${textClr}`}>
        <Palette size={20} />
        <div>
          <div className="text-xs opacity-70">Studio</div>
          <div className="font-unbounded text-sm font-semibold">{att.name || "Visit studio"}</div>
        </div>
      </Link>
    );
  }
  if (att.kind === "commission") {
    return (
      <Link to={`/commissions/${att.ref_id}`} className={`flex items-center gap-3 p-3 ${textClr}`}>
        <Palette size={18} />
        <div>
          <div className="text-xs opacity-70">Commission · {att.status}</div>
          <div className="font-unbounded text-sm font-semibold">{att.subject}</div>
        </div>
      </Link>
    );
  }
  if (att.kind === "auction") {
    return (
      <Link to={`/auctions/${att.ref_id}`} className={`flex items-center gap-3 p-3 ${textClr}`}>
        <div>
          <div className="text-xs opacity-70">Auction · {att.status}</div>
          <div className="font-unbounded text-sm font-semibold">{att.title}</div>
          {att.current_bid != null && <div className="text-xs opacity-70">Current bid ${Number(att.current_bid).toLocaleString()}</div>}
        </div>
      </Link>
    );
  }
  if (att.kind === "offer") {
    return <div className={`p-3 ${textClr}`}><div className="text-xs opacity-70">Offer · {att.status}</div><div className="font-anton text-lg">${Number(att.amount || 0).toLocaleString()}</div></div>;
  }
  if (att.kind === "order") {
    return (
      <Link to={`/orders/${att.ref_id}`} className={`p-3 ${textClr}`}>
        <div className="text-xs opacity-70">Order · {att.status || "pending"}</div>
        <div className="font-anton text-lg">${Number(att.total || 0).toLocaleString()}</div>
      </Link>
    );
  }
  return null;
}
