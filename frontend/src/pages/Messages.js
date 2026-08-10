import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";

export function MessagesInbox() {
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get("/messages/threads").then((r) => setThreads(r.data)).finally(() => setLoading(false));
  }, []);
  return (
    <div data-testid="messages-inbox" className="max-w-3xl mx-auto px-6 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Inbox</div>
      <h1 className="font-anton text-6xl md:text-7xl uppercase mt-4">Messages</h1>
      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        threads.length === 0 ? (
          <div className="border border-dashed border-white/10 py-16 text-center mt-12 rounded-sm">
            <div className="label-caps text-zinc-500">No conversations yet.</div>
            <div className="text-sm text-zinc-400 mt-4">Message an artist from their portfolio to start.</div>
          </div>
        ) : (
          <div className="mt-8 divide-y divide-white/8 border border-white/8 rounded-sm">
            {threads.map((t) => (
              <Link key={t.thread_key} to={`/messages/${t.other_user_id}`}
                data-testid={`thread-${t.other_user_id}`}
                className="flex items-center gap-4 p-5 hover:bg-white/[0.03] transition-colors">
                <div className="w-12 h-12 rounded-full bg-[#7C3AED]/20 flex items-center justify-center font-anton text-xl">
                  {t.other_user_name[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="font-unbounded font-semibold truncate">{t.other_user_name}</div>
                    <div className="text-xs text-zinc-500 flex-shrink-0">{new Date(t.last_at).toLocaleDateString()}</div>
                  </div>
                  <div className="text-sm text-zinc-400 truncate mt-1">{t.last_message}</div>
                </div>
                {t.unread > 0 && <div className="badge-lime">{t.unread}</div>}
              </Link>
            ))}
          </div>
        )}
    </div>
  );
}

export function MessageThread() {
  const { userId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  const load = () => api.get(`/messages/thread/${userId}`).then((r) => setData(r.data));
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [userId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [data]);

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try {
      await api.post("/messages", { to_user_id: userId, text });
      setText(""); await load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setSending(false);
  };

  if (!data) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;

  return (
    <div data-testid="message-thread" className="max-w-3xl mx-auto px-6 pt-16 pb-32">
      <button onClick={() => nav("/messages")} className="label-caps text-zinc-500 hover:text-[#CCFF00] mb-6">← Inbox</button>
      <div className="border border-white/8 rounded-sm">
        <div className="p-4 border-b border-white/8 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[#CCFF00]/20 flex items-center justify-center font-anton">
            {data.other?.name?.[0] || "?"}
          </div>
          <div>
            <div className="font-unbounded font-semibold">{data.other?.name}</div>
            <div className="label-caps mt-0.5">{data.other?.role}</div>
          </div>
        </div>
        <div className="h-[420px] overflow-y-auto p-4 space-y-3 bg-[#0A0A0C]">
          {data.messages.length === 0 && <div className="text-zinc-500 label-caps text-center py-16">Say hi.</div>}
          {data.messages.map((m) => (
            <div key={m.id} data-testid={`msg-${m.id}`}
              className={`flex ${m.from_id === user.id ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[70%] px-4 py-2.5 rounded-sm text-sm ${m.from_id === user.id ? "bg-[#CCFF00] text-black" : "bg-[#1A1A1E] text-white"}`}>
                {m.text}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form onSubmit={send} className="p-4 border-t border-white/8 flex gap-2">
          <input data-testid="message-input" value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 bg-transparent border border-white/12 px-3 py-2 text-sm outline-none focus:border-[#CCFF00] rounded-sm" />
          <button data-testid="message-send" disabled={sending} className="btn-lime !py-2 !text-xs">Send</button>
        </form>
      </div>
    </div>
  );
}
