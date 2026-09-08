import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Gavel, Clock, TrendingUp, Trophy, CreditCard, Radio } from "lucide-react";
import { useLive } from "../hooks/useLive";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

function useCountdown(endIso) {
  const [remaining, setRemaining] = useState(() => Math.max(0, new Date(endIso) - new Date()));
  useEffect(() => {
    const t = setInterval(() => setRemaining(Math.max(0, new Date(endIso) - new Date())), 1000);
    return () => clearInterval(t);
  }, [endIso]);
  const sec = Math.floor(remaining / 1000);
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return { d, h, m, s, done: remaining === 0 };
}

function CountdownBadge({ endIso, small }) {
  const { d, h, m, s, done } = useCountdown(endIso);
  if (done) return <div className={`badge-coral ${small ? "" : "!text-sm !px-3 !py-1.5"}`}>Ended</div>;
  const cls = small ? "font-anton text-lg" : "font-anton text-3xl md:text-5xl";
  return (
    <div className="flex items-baseline gap-2" data-testid="countdown">
      {d > 0 && <><span className={cls}>{d}</span><span className="label-caps">d</span></>}
      <span className={cls}>{String(h).padStart(2, "0")}</span><span className="label-caps">h</span>
      <span className={cls}>{String(m).padStart(2, "0")}</span><span className="label-caps">m</span>
      <span className={cls}>{String(s).padStart(2, "0")}</span><span className="label-caps">s</span>
    </div>
  );
}

export function AuctionsList() {
  const [live, setLive] = useState([]);
  const [scheduled, setScheduled] = useState([]);
  const [ended, setEnded] = useState([]);
  const [tab, setTab] = useState("live");
  useEffect(() => {
    const loadAll = () => {
      api.get("/auctions?status=live").then((r) => setLive(r.data));
      api.get("/auctions?status=scheduled").then((r) => setScheduled(r.data));
      api.get("/auctions?status=ended").then((r) => setEnded(r.data));
    };
    loadAll();
    const t = setInterval(loadAll, 5000);
    return () => clearInterval(t);
  }, []);
  const list = tab === "live" ? live : tab === "scheduled" ? scheduled : ended;
  return (
    <div data-testid="auctions-page" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="mb-8">
        <div className="label-caps text-[#7C3AED]"><Gavel size={12} className="inline mr-2" /> Bidding Room</div>
        <h1 className="font-anton text-6xl md:text-9xl uppercase mt-4 leading-[0.85]">Auctions</h1>
        <p className="text-zinc-400 mt-4 max-w-xl">Real-time bidding. When the clock runs out, the highest bid wins.</p>
      </div>
      <div className="flex gap-1 border-b border-white/8 mb-10">
        {[["live", `Live (${live.length})`], ["scheduled", `Scheduled (${scheduled.length})`], ["ended", `Ended (${ended.length})`]].map(([k, l]) => (
          <button key={k} data-testid={`auction-tab-${k}`} onClick={() => setTab(k)}
            className={`label-caps px-4 py-3 border-b-2 ${tab === k ? "border-[#CCFF00] text-white" : "border-transparent text-zinc-500"}`}>{l}</button>
        ))}
      </div>
      {list.length === 0 ? (
        <div className="border border-dashed border-white/10 py-24 text-center label-caps text-zinc-500 rounded-sm">
          {tab === "live" ? "No live auctions right now." : tab === "scheduled" ? "No auctions scheduled." : "No completed auctions yet."}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {list.map((a) => <AuctionCard key={a.id} a={a} />)}
        </div>
      )}
    </div>
  );
}

function AuctionCard({ a }) {
  const { done } = useCountdown(a.end_at);
  const isScheduled = a.status === "scheduled";
  return (
    <Link to={`/auctions/${a.id}`} data-testid={`auction-card-${a.id}`}
      className="block border border-white/8 hover-lift-card group bg-[#121214] rounded-sm">
      <div className="aspect-[4/3] overflow-hidden bg-black relative">
        <img src={resolveImg(a.artwork?.images?.[0])} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" alt="" />
        <div className="absolute top-3 left-3">
          {isScheduled ? <div className="badge-violet !bg-[#F5A623]/20 !text-[#F5A623] !border-[#F5A623]/40">Scheduled</div> : <div className="badge-violet">Live · {a.bid_count} bids</div>}
        </div>
        {done && !isScheduled && <div className="absolute inset-0 bg-black/60 flex items-center justify-center"><div className="badge-coral !text-sm !px-4 !py-2">Ending...</div></div>}
      </div>
      <div className="p-5">
        <div className="font-unbounded font-semibold text-lg">{a.artwork?.title}</div>
        <div className="text-xs text-zinc-500 mt-1">by {a.seller?.name}</div>
        <div className="flex items-baseline justify-between mt-4">
          <div>
            <div className="label-caps">{isScheduled ? "Starts at" : "Current bid"}</div>
            {isScheduled ? (
              <div className="font-anton text-xl mt-1">{new Date(a.start_at).toLocaleString()}</div>
            ) : (
              <div className="font-anton text-3xl text-[#CCFF00] mt-1">${Number(a.current_bid || a.start_price).toLocaleString()}</div>
            )}
          </div>
          <div className="text-right">
            <div className="label-caps">{isScheduled ? "Starts in" : "Ends in"}</div>
            <div className="mt-1"><CountdownBadge endIso={isScheduled ? a.start_at : a.end_at} small /></div>
          </div>
        </div>
      </div>
    </Link>
  );
}

export function AuctionDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [a, setA] = useState(null);
  const [bids, setBids] = useState([]);
  const [amount, setAmount] = useState("");
  const [placing, setPlacing] = useState(false);

  const load = () => {
    api.get(`/auctions/${id}`).then((r) => { setA(r.data); }).catch(() => nav("/auctions"));
    api.get(`/auctions/${id}/bids`).then((r) => setBids(r.data));
  };
  const liveConnected = useLive([`auction:${id}`], (ev) => { if (ev.type === "bid") load(); });
  useEffect(() => {
    load();
    const t = setInterval(load, liveConnected ? 20000 : 3000);
    return () => clearInterval(t);
  }, [id, liveConnected]);

  const placeBid = async (e) => {
    e.preventDefault();
    if (!user) { toast("Sign in to bid"); return; }
    setPlacing(true);
    try {
      await api.post(`/auctions/${id}/bid`, { amount: Number(amount) });
      toast.success("Bid placed");
      setAmount("");
      load();
    } catch (er) { toast.error(er?.response?.data?.detail || "Bid failed"); }
    setPlacing(false);
  };

  if (!a) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  const isSeller = user?.id === a.seller_id;
  const minNext = Math.max(a.start_price, (a.current_bid || 0) + 1);
  const isWinning = user?.id === a.current_bidder_id;
  const iWon = a.status === "ended" && a.winner_id === user?.id;

  return (
    <div data-testid="auction-detail" className="max-w-[1600px] mx-auto px-4 md:px-12 pt-6 md:pt-12 pb-32 overflow-x-hidden">
      <div className="grid md:grid-cols-12 gap-6 md:gap-10">
        <div className="md:col-span-7 min-w-0">
          <div className="aspect-[4/3] bg-black overflow-hidden border border-white/8 rounded-sm">
            <img src={resolveImg(a.artwork?.images?.[0])} alt="" className="w-full h-full object-cover" />
          </div>
          <div className="mt-4">
            <div className="label-caps text-[#7C3AED] flex items-center gap-3">Auctioning
              {liveConnected && <span data-testid="live-indicator" className="inline-flex items-center gap-1 text-[10px] text-[#CCFF00]"><Radio size={10} className="animate-pulse" /> LIVE</span>}
            </div>
            <div className="font-anton text-4xl mt-2">{a.artwork?.title}</div>
            <div className="text-sm text-zinc-500 mt-1">by <Link to={`/artist/${a.seller?.id}`} className="text-[#CCFF00]">{a.seller?.name}</Link></div>
          </div>
        </div>

        <div className="md:col-span-5 min-w-0">
          <div className="glass-card p-4 md:p-6 rounded-sm">
            {a.status === "scheduled" ? (
              <>
                <div className="label-caps text-[#F5A623]">Starts in</div>
                <div className="mt-2"><CountdownBadge endIso={a.start_at} /></div>
                <div className="text-xs text-zinc-500 mt-3">Bidding opens {new Date(a.start_at).toLocaleString()}</div>
              </>
            ) : a.status === "live" ? (
              <>
                <div className="label-caps text-[#7C3AED]">Ends in</div>
                <div className="mt-2"><CountdownBadge endIso={a.end_at} /></div>
              </>
            ) : a.status === "cancelled" ? (
              <div className="badge-coral">Cancelled · No Payment</div>
            ) : a.payment_deadline && !a.paid ? (
              <>
                <div className="label-caps text-[#F5A623]">Winner must pay in</div>
                <div className="mt-2"><CountdownBadge endIso={a.payment_deadline} /></div>
                <div className="text-xs text-zinc-500 mt-3">Payment window: 48 hours. If not paid, the auction passes to the next-highest bidder.</div>
              </>
            ) : (
              <div className="badge-coral">Auction Ended</div>
            )}
            <div className="mt-8 border-t border-white/8 pt-6">
              <div className="label-caps">Current bid</div>
              <div className="font-anton text-5xl md:text-6xl text-[#CCFF00] mt-2 break-words">${Number(a.current_bid || a.start_price).toLocaleString()}</div>
              <div className="text-xs text-zinc-500 mt-2">
                {a.bid_count} bid{a.bid_count === 1 ? "" : "s"} · Start ${Number(a.start_price).toLocaleString()}
                {a.reserve_price > 0 && ` · Reserve $${Number(a.reserve_price).toLocaleString()}`}
              </div>
              {a.current_bidder_name && (
                <div className="mt-3 label-caps">
                  Leading: <span className={isWinning ? "text-[#CCFF00]" : "text-white"}>{a.current_bidder_name}</span>
                  {isWinning && <span className="ml-2 text-[#CCFF00]">← you</span>}
                </div>
              )}
            </div>

            {a.status === "live" && !isSeller && (
              <>
                <form onSubmit={placeBid} className="mt-6">
                  <div className="label-caps mb-2">Your bid (min ${minNext.toLocaleString()})</div>
                  <div className="flex gap-2">
                    <input data-testid="bid-input" type="number" min={minNext} step="1" required
                      value={amount} onChange={(e) => setAmount(e.target.value)}
                      className="flex-1 min-w-0 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none focus:border-[#CCFF00] font-unbounded" />
                    <button data-testid="bid-submit" disabled={placing} className="btn-lime">
                      {placing ? "..." : "Bid"}
                    </button>
                  </div>
                </form>
                <ProxyBidPanel auctionId={a.id} minNext={minNext} onSet={load} />
                <WatchToggle auctionId={a.id} />
              </>
            )}
            {a.status === "live" && isSeller && <div className="mt-6 label-caps text-zinc-500">You're the seller.</div>}
            {iWon && !a.paid && (
              <div className="mt-6 p-4 border border-[#CCFF00] rounded-sm bg-[#CCFF00]/5" data-testid="winner-banner">
                <div className="badge-lime"><Trophy size={12} className="inline mr-1" /> You won</div>
                <div className="text-sm mt-3 text-zinc-200">Complete payment to release the piece to Art Core for shipping.</div>
                <PayAuctionButton auctionId={a.id} amount={a.final_price || a.current_bid} />
              </div>
            )}
            {iWon && a.paid && (
              <div className="mt-6 p-4 border border-white/10 rounded-sm" data-testid="winner-paid">
                <div className="badge-lime">Paid</div>
                <div className="text-sm mt-3 text-zinc-200">Your win is settled. Art Core is coordinating delivery.</div>
              </div>
            )}
          </div>

          <div className="mt-6 glass-card p-6 rounded-sm">
            <div className="label-caps mb-4 flex items-center gap-2"><TrendingUp size={12} /> Bid History</div>
            {bids.length === 0 ? <div className="text-zinc-500 text-sm">No bids yet.</div> : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {bids.map((b) => (
                  <div key={b.id} data-testid={`bid-${b.id}`} className="flex justify-between text-sm py-2 border-b border-white/5">
                    <div>{b.user_name}</div>
                    <div className="font-anton text-[#CCFF00]">${Number(b.amount).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function CreateAuction() {
  const nav = useNavigate();
  const { user } = useAuth();
  const [artworks, setArtworks] = useState([]);
  const [form, setForm] = useState({ artwork_id: "", start_price: 100, reserve_price: 0, duration_minutes: 60, when: "now", start_at: "" });
  useEffect(() => {
    api.get("/artworks/mine").then((r) => setArtworks(r.data.filter((a) => a.status === "live")));
  }, []);
  const submit = async (e) => {
    e.preventDefault();
    if (!form.artwork_id) { toast.error("Pick an artwork"); return; }
    try {
      const payload = {
        artwork_id: form.artwork_id,
        start_price: Number(form.start_price),
        reserve_price: Number(form.reserve_price),
        duration_minutes: Number(form.duration_minutes),
      };
      if (form.when === "scheduled" && form.start_at) {
        payload.start_at = new Date(form.start_at).toISOString();
      }
      const r = await api.post("/auctions", payload);
      toast.success(form.when === "scheduled" ? "Auction scheduled" : "Auction live");
      nav(`/auctions/${r.data.id}`);
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
  };
  const minDT = new Date(Date.now() + 60_000).toISOString().slice(0, 16);
  return (
    <div data-testid="create-auction" className="max-w-2xl mx-auto px-6 pt-16 pb-32">
      <div className="label-caps text-[#7C3AED]"><Gavel size={12} className="inline mr-2" /> New Auction</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 mb-10">Launch Auction</h1>
      <form onSubmit={submit} className="space-y-5">
        <label className="block">
          <div className="label-caps mb-2">Artwork (live only)</div>
          <select data-testid="auction-artwork" value={form.artwork_id} onChange={(e) => setForm({ ...form, artwork_id: e.target.value })} required
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none">
            <option value="">— Select —</option>
            {artworks.map((a) => <option key={a.id} value={a.id}>{a.title} (${a.price})</option>)}
          </select>
          {artworks.length === 0 && <div className="text-xs text-zinc-500 mt-2">You need at least one live artwork. <Link to="/studio/upload" className="text-[#CCFF00]">Upload one</Link></div>}
        </label>
        <label className="block">
          <div className="label-caps mb-2">Start price (USD)</div>
          <input data-testid="auction-start-price" type="number" min="1" required value={form.start_price} onChange={(e) => setForm({ ...form, start_price: e.target.value })}
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" />
        </label>
        <label className="block">
          <div className="label-caps mb-2">Reserve price (0 = none)</div>
          <input data-testid="auction-reserve-price" type="number" min="0" value={form.reserve_price} onChange={(e) => setForm({ ...form, reserve_price: e.target.value })}
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" />
        </label>
        <label className="block">
          <div className="label-caps mb-2">Duration</div>
          <select data-testid="auction-duration" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none">
            <option value={15}>15 minutes</option>
            <option value={60}>1 hour</option>
            <option value={60 * 24}>24 hours</option>
            <option value={60 * 24 * 3}>3 days</option>
            <option value={60 * 24 * 7}>7 days</option>
          </select>
        </label>
        <div>
          <div className="label-caps mb-2">When</div>
          <div className="flex gap-2">
            {[["now", "Start now"], ["scheduled", "Schedule for later"]].map(([k, l]) => (
              <button type="button" key={k} data-testid={`when-${k}`}
                onClick={() => setForm({ ...form, when: k })}
                className={`label-caps px-4 py-2 border rounded-sm ${form.when === k ? "border-[#CCFF00] text-[#CCFF00]" : "border-white/12 text-zinc-400"}`}>{l}</button>
            ))}
          </div>
          {form.when === "scheduled" && (
            <input data-testid="auction-start-at" type="datetime-local" min={minDT} required value={form.start_at}
              onChange={(e) => setForm({ ...form, start_at: e.target.value })}
              className="w-full mt-3 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none" />
          )}
        </div>
        <button data-testid="auction-submit" className="btn-lime mt-6">
          {form.when === "scheduled" ? "Schedule Auction" : "Launch Live Auction"}
        </button>
      </form>
    </div>
  );
}

function PayAuctionButton({ auctionId, amount }) {
  const [busy, setBusy] = useState(false);
  const pay = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/payments/auctions/${auctionId}/pay`, { origin_url: ORIGIN });
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Payment failed"); setBusy(false); }
  };
  return (
    <button data-testid="pay-auction-btn" onClick={pay} disabled={busy} className="btn-lime mt-4">
      <CreditCard size={14} className="mr-2" />
      {busy ? "Redirecting..." : `Pay $${Number(amount).toLocaleString()} Now`}
    </button>
  );
}

function ProxyBidPanel({ auctionId, minNext, onSet }) {
  const [mine, setMine] = useState(null);
  const [max, setMax] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/auctions/${auctionId}/proxy-bid/mine`).then((r) => setMine(r.data)).catch(() => {});
  useEffect(() => { load(); }, [auctionId]);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/auctions/${auctionId}/proxy-bid`, { max_amount: Number(max) });
      toast.success("Auto-bid set");
      setMax(""); load(); onSet?.();
    } catch (er) { toast.error(er?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };
  const cancel = async () => {
    try { await api.delete(`/auctions/${auctionId}/proxy-bid`); toast.success("Auto-bid off"); load(); }
    catch { toast.error("Failed"); }
  };
  return (
    <div className="mt-4 pt-4 border-t border-white/8" data-testid="proxy-panel">
      <div className="label-caps mb-2">Auto-bid up to</div>
      {mine?.active ? (
        <div className="flex items-center gap-3">
          <div className="font-anton text-2xl text-[#7C3AED]">${Number(mine.max_amount).toLocaleString()}</div>
          <button data-testid="proxy-cancel" onClick={cancel} className="label-caps text-[#FF4D4D] hover:underline">Turn off</button>
        </div>
      ) : (
        <form onSubmit={submit} className="flex gap-2">
          <input data-testid="proxy-input" type="number" min={minNext} step="1" placeholder={`min $${minNext}`} value={max} onChange={(e) => setMax(e.target.value)}
            className="flex-1 min-w-0 bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#7C3AED]" />
          <button data-testid="proxy-set" disabled={busy || !max} className="btn-violet !py-2 !text-xs">Set Max</button>
        </form>
      )}
      <div className="text-xs text-zinc-500 mt-2">We'll bid for you in increments up to this ceiling.</div>
    </div>
  );
}

function WatchToggle({ auctionId }) {
  const [state, setState] = useState({ watching: false, count: 0 });
  const load = () => api.get(`/auctions/${auctionId}/watch`).then((r) => setState(r.data)).catch(() => {});
  useEffect(() => { load(); }, [auctionId]);
  const toggle = async () => {
    try {
      if (state.watching) await api.delete(`/auctions/${auctionId}/watch`);
      else await api.post(`/auctions/${auctionId}/watch`);
      load();
    } catch { toast.error("Failed"); }
  };
  return (
    <div className="mt-4 pt-4 border-t border-white/8 flex items-center justify-between gap-3 flex-wrap" data-testid="watch-panel">
      <div>
        <div className="label-caps">Watching · {state.count}</div>
        <div className="text-xs text-zinc-500 mt-1">Get notified on leader changes and 6h before payment deadline.</div>
      </div>
      <button data-testid="watch-toggle" onClick={toggle} className={state.watching ? "btn-lime !py-2 !text-xs" : "btn-ghost !py-2 !text-xs"}>
        {state.watching ? "Watching ✓" : "Watch"}
      </button>
    </div>
  );
}
