import { useTranslation } from "react-i18next";
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../api";
import { Bell, Gavel, Trophy, Palette, UserPlus, Check, Trash2, MessageSquare, Heart, BellRing, BellOff, Loader2, Settings2, AtSign, MapPin } from "lucide-react";
import usePushSubscription from "../hooks/usePushSubscription";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

const KIND_META = {
  outbid: { label: "You were outbid", icon: <Gavel size={14} />, color: "#FF4D4D" },
  auction_won: { label: "You won an auction", icon: <Trophy size={14} />, color: "#CCFF00" },
  auction_sold: { label: "Your artwork sold", icon: <Trophy size={14} />, color: "#CCFF00" },
  auction_paid: { label: "Auction paid — payout queued", icon: <Trophy size={14} />, color: "#CCFF00" },
  auction_forfeited: { label: "Auction win forfeited", icon: <Gavel size={14} />, color: "#FF4D4D" },
  auction_cancelled: { label: "Auction cancelled — no payer", icon: <Gavel size={14} />, color: "#FF4D4D" },
  auction_deadline_soon: { label: "Payment deadline in <6h", icon: <Bell size={14} />, color: "#F5A623" },
  watched_auction_leader: { label: "Watched auction has a new leader", icon: <Bell size={14} />, color: "#7C3AED" },
  commission_request: { label: "New commission request", icon: <Palette size={14} />, color: "#7C3AED" },
  commission_accept: { label: "Commission accepted", icon: <Check size={14} />, color: "#CCFF00" },
  commission_decline: { label: "Commission declined", icon: <Palette size={14} />, color: "#FF4D4D" },
  commission_counter: { label: "Counter offer sent", icon: <Palette size={14} />, color: "#F5A623" },
  commission_progress: { label: "Commission progress update", icon: <Palette size={14} />, color: "#00E5FF" },
  commission_delivered: { label: "Commission delivered", icon: <Palette size={14} />, color: "#CCFF00" },
  commission_approved: { label: "Commission approved", icon: <Check size={14} />, color: "#CCFF00" },
  commission_deposit: { label: "Commission deposit received", icon: <Check size={14} />, color: "#CCFF00" },
  commission_paid: { label: "Commission paid in full", icon: <Check size={14} />, color: "#CCFF00" },
  order_confirmed: { label: "Order confirmed", icon: <Check size={14} />, color: "#CCFF00" },
  order_shipped: { label: "Order shipped", icon: <Bell size={14} />, color: "#7C3AED" },
  payout_released: { label: "Payout released", icon: <Check size={14} />, color: "#CCFF00" },
  artwork_sold: { label: "Your artwork sold", icon: <Trophy size={14} />, color: "#CCFF00" },
  offer_received: { label: "New offer received", icon: <Palette size={14} />, color: "#7C3AED" },
  offer_accept: { label: "Offer accepted", icon: <Check size={14} />, color: "#CCFF00" },
  offer_decline: { label: "Offer declined", icon: <Palette size={14} />, color: "#FF4D4D" },
  offer_counter: { label: "Counter offer received", icon: <Palette size={14} />, color: "#F5A623" },
  offer_accepted_by_buyer: { label: "Buyer accepted counter", icon: <Check size={14} />, color: "#CCFF00" },
  offer_withdrawn: { label: "Offer withdrawn", icon: <Palette size={14} />, color: "#71717A" },
  offer_paid: { label: "Offer paid — order created", icon: <Check size={14} />, color: "#CCFF00" },
  offer_expired: { label: "Offer expired", icon: <Palette size={14} />, color: "#71717A" },
  new_review: { label: "New review on your artwork", icon: <Check size={14} />, color: "#CCFF00" },
  new_follower: { label: "New follower", icon: <UserPlus size={14} />, color: "#7C3AED" },
  new_comment: { label: "New comment on your artwork", icon: <MessageSquare size={14} />, color: "#CCFF00" },
  comment_reply: { label: "Replied to your comment", icon: <MessageSquare size={14} />, color: "#7C3AED" },
  artwork_shared: { label: "Your artwork was shared", icon: <Bell size={14} />, color: "#00E5FF" },
  mentioned_in_comment: { label: "Mentioned you", icon: <Bell size={14} />, color: "#F5A623" },
  mentioned_in_post_comment: { label: "Mentioned you", icon: <Bell size={14} />, color: "#F5A623" },
  mentioned_in_post: { label: "Mentioned you in a post", icon: <Bell size={14} />, color: "#F5A623" },
  post_liked: { label: "Liked your post", icon: <Heart size={14} />, color: "#FF4D4D" },
  post_comment: { label: "Commented on your post", icon: <MessageSquare size={14} />, color: "#CCFF00" },
  new_message: { label: "New message", icon: <MessageSquare size={14} />, color: "#7C3AED" },
  auction_ending: { label: "Auction ending soon", icon: <Gavel size={14} />, color: "#F5A623" },
  event_rsvp: { label: "New RSVP to your event", icon: <MapPin size={14} />, color: "#CCFF00" },
  event_cancelled: { label: "An event was cancelled", icon: <MapPin size={14} />, color: "#FF4D4D" },
  event_ticket_paid: { label: "Ticket purchased", icon: <Check size={14} />, color: "#CCFF00" },
  event_reminder: { label: "Event happening soon", icon: <MapPin size={14} />, color: "#F5A623" },
  event_waitlist_joined: { label: "You're on the waitlist", icon: <MapPin size={14} />, color: "#7C3AED" },
  event_waitlist_open: { label: "A seat opened up", icon: <MapPin size={14} />, color: "#CCFF00" },
  event_broadcast: { label: "Message from event host", icon: <MapPin size={14} />, color: "#7C3AED" },
  dispute_opened: { label: "Order dispute opened", icon: <Bell size={14} />, color: "#FF4D4D" },
  dispute_resolved: { label: "Dispute resolved", icon: <Check size={14} />, color: "#CCFF00" },
  order_delivered_confirm: { label: "Did your order arrive? Confirm now", icon: <Bell size={14} />, color: "#F5A623" },
  order_received_confirmed: { label: "Buyer confirmed receipt — payout scheduled", icon: <Check size={14} />, color: "#CCFF00" },
  order_auto_confirmed: { label: "Order auto-confirmed delivered", icon: <Check size={14} />, color: "#CCFF00" },
  order_not_received: { label: "Buyer reports item not received", icon: <Bell size={14} />, color: "#FF4D4D" },
  referral_joined: { label: "An artist joined with your invite link", icon: <UserPlus size={14} />, color: "#CCFF00" },
  referral_reward: { label: "Your invitee made a sale — your next sale is fee-free", icon: <Check size={14} />, color: "#CCFF00" },
  referral_badge: { label: "First sale! You earned the Crew badge", icon: <Check size={14} />, color: "#7C3AED" },
  dispute_auto_warning: { label: "Dispute auto-resolves in 2 days — review it", icon: <Bell size={14} />, color: "#F5A623" },
  dispute_auto_failed: { label: "Dispute auto-resolve failed — needs you", icon: <Bell size={14} />, color: "#FF4D4D" },
  followed_new_artwork: { label: "New work from an artist you follow", icon: <Heart size={14} />, color: "#CCFF00" },
  followed_new_post: { label: "New post from an artist you follow", icon: <Heart size={14} />, color: "#CCFF00" },
  followed_new_event: { label: "An artist you follow announced an event", icon: <MapPin size={14} />, color: "#FF4D4D" },
  report_opened: { label: "New content report", icon: <Bell size={14} />, color: "#FF4D4D" },
  report_resolved: { label: "Your report was reviewed", icon: <Check size={14} />, color: "#CCFF00" },
  moderation_action: { label: "Moderation notice", icon: <Bell size={14} />, color: "#F5A623" },
};

export default function Notifications() {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [prefs, setPrefs] = useState(null);
  const [showPrefs, setShowPrefs] = useState(false);
  const push = usePushSubscription();

  const loadPrefs = () => api.get("/notifications/prefs").then((r) => setPrefs(r.data)).catch(() => setPrefs(null));
  useEffect(() => { loadPrefs(); }, []);

  const togglePref = async (key) => {
    if (!prefs) return;
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next); // optimistic
    try {
      const r = await api.patch("/notifications/prefs", { categories: next });
      setPrefs(r.data);
    } catch {
      setPrefs(prefs); // revert
    }
  };

  const load = () => api.get("/notifications?limit=100").then((r) => setItems(r.data)).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const markAll = async () => {
    await api.post("/notifications/read", {});
    load();
  };
  const del = async (id) => {
    await api.delete(`/notifications/${id}`);
    load();
  };

  const unread = items.filter((n) => !n.read).length;

  return (
    <div data-testid="notifications-page" className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="flex items-end justify-between flex-wrap gap-4 mb-10">
        <div>
          <div className="label-caps text-[#CCFF00]"><Bell size={12} className="inline mr-2" /> Inbox</div>
          <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4">{t("notif.title")}</h1>
          <div className="label-caps text-zinc-500 mt-2">{unread} unread</div>
        </div>
        {unread > 0 && (
          <button data-testid="mark-all-read" onClick={markAll} className="btn-ghost !py-2 !text-xs">Mark all read</button>
        )}
        <button data-testid="toggle-prefs" onClick={() => setShowPrefs(!showPrefs)} className="btn-ghost !py-2 !text-xs flex items-center gap-1">
          <Settings2 size={12} /> {showPrefs ? t("notif.hide_prefs") : t("notif.prefs")}
        </button>
      </div>

      {/* Category preferences (mute categories) */}
      {showPrefs && prefs && (
        <div data-testid="prefs-card" className="border border-white/8 rounded-sm p-4 mb-6 bg-[#121214]">
          <div className="label-caps text-zinc-400 mb-3">What do you want alerts for?</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {[
              { key: "dm", label: "Messages", icon: <MessageSquare size={12} />, color: "#7C3AED" },
              { key: "bid", label: "Auctions & Bids", icon: <Gavel size={12} />, color: "#FF4D4D" },
              { key: "offer", label: "Offers", icon: <Palette size={12} />, color: "#F5A623" },
              { key: "commission", label: "Commissions", icon: <Palette size={12} />, color: "#7C3AED" },
              { key: "follow", label: "New Followers", icon: <UserPlus size={12} />, color: "#00E5FF" },
              { key: "mention", label: "Mentions", icon: <AtSign size={12} />, color: "#CCFF00" },
              { key: "post", label: "Post Activity", icon: <Heart size={12} />, color: "#FF6EC7" },
              { key: "event", label: "Events", icon: <MapPin size={12} />, color: "#FF4D4D" },
            ].map((c) => {
              const on = prefs[c.key] !== false;
              return (
                <button
                  key={c.key}
                  data-testid={`pref-${c.key}`}
                  onClick={() => togglePref(c.key)}
                  className="flex items-center gap-2 border rounded-sm px-3 py-2 text-left transition-colors"
                  style={{
                    borderColor: on ? c.color : "rgba(255,255,255,0.08)",
                    background: on ? `${c.color}12` : "transparent",
                  }}>
                  <span className="p-1 rounded-sm flex-shrink-0" style={{ background: `${c.color}22`, color: c.color }}>{c.icon}</span>
                  <span className="text-xs flex-1">{c.label}</span>
                  <span className={`w-8 h-4 rounded-full flex-shrink-0 flex items-center transition-colors ${on ? "bg-[#CCFF00]" : "bg-white/10"}`}>
                    <span className={`w-3 h-3 rounded-full bg-black transition-transform ${on ? "translate-x-4" : "translate-x-0.5"}`} />
                  </span>
                </button>
              );
            })}
          </div>
          <div className="text-xs text-zinc-500 mt-3">Toggles apply to push notifications. Your in-app inbox always receives everything.</div>
        </div>
      )}

      {/* Push notification toggle */}
      {push.supported && (
        <div data-testid="push-card" className="border border-white/8 rounded-sm p-4 mb-6 flex items-center gap-4 bg-[#121214]">
          <div className={`p-2 rounded-sm flex-shrink-0 ${push.subscribed ? "bg-[#CCFF00]/20 text-[#CCFF00]" : "bg-white/[0.05] text-zinc-400"}`}>
            {push.subscribed ? <BellRing size={18} /> : <BellOff size={18} />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-unbounded font-semibold text-sm">
              {push.subscribed ? "Push notifications on" : "Turn on push notifications"}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">
              {push.subscribed
                ? "You'll get instant alerts for messages, bids, and offers — even when the app is closed."
                : "Instant alerts for new messages, outbid warnings, and offer updates."}
            </div>
          </div>
          {push.subscribed ? (
            <div className="flex gap-2 flex-shrink-0">
              <button data-testid="push-test-btn" onClick={push.test} disabled={push.loading}
                className="btn-ghost !py-2 !px-3 text-xs">Send test</button>
              <button data-testid="push-disable-btn" onClick={push.disable} disabled={push.loading}
                className="btn-ghost !py-2 !px-3 text-xs">
                {push.loading ? <Loader2 size={12} className="animate-spin" /> : "Turn off"}
              </button>
            </div>
          ) : (
            <button data-testid="push-enable-btn" onClick={push.enable} disabled={push.loading}
              className="btn-lime !py-2 !px-4 text-xs flex-shrink-0">
              {push.loading ? <Loader2 size={12} className="animate-spin" /> : "Enable"}
            </button>
          )}
        </div>
      )}

      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        items.length === 0 ? (
          <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
            <div className="label-caps text-zinc-500">{t("notif.empty")}</div>
            <div className="text-sm text-zinc-400 mt-4">{t("notif.empty_sub")}</div>
          </div>
        ) : (
          <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
            {items.map((n) => {
              const base = KIND_META[n.kind] || { label: n.kind, icon: <Bell size={14} />, color: "#A1A1AA" };
              const meta = { ...base, label: t(`notif.${n.kind}`, { defaultValue: base.label }) };
              const to = n.commission?.id ? `/commissions/${n.commission.id}` :
                         n.auction?.id ? `/auctions/${n.auction.id}` :
                         n.offer?.id ? "/offers" :
                         n.order?.id ? `/orders/${n.order.id}` :
                         n.event_id ? `/events/${n.event_id}` :
                         n.kind === "new_message" && n.other?.id ? `/messages/${n.other.id}` :
                         n.artwork?.id ? `/artwork/${n.artwork.id}` :
                         n.post?.id && n.other?.id ? `/artist/${n.other.id}` :
                         n.other?.id ? `/artist/${n.other.id}` : null;
              const inner = (
                <div className={`p-4 flex items-start gap-4 hover:bg-white/[0.03] transition-colors ${!n.read ? "border-l-2 border-[#CCFF00]" : ""}`}>
                  <div className="p-2 rounded-sm mt-0.5" style={{ background: `${meta.color}20`, color: meta.color }}>{meta.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="font-unbounded font-semibold text-sm">{meta.label}</div>
                      <div className="text-xs text-zinc-500 flex-shrink-0">{new Date(n.created_at).toLocaleString()}</div>
                    </div>
                    <div className="text-sm text-zinc-300 mt-1 truncate">
                      {n.other?.name && <span>{n.other.name}</span>}
                      {n.other?.name && (n.artwork?.title || n.commission?.subject) && <span className="text-zinc-500"> · </span>}
                      {n.artwork?.title && <span>{n.artwork.title}</span>}
                      {n.commission?.subject && <span>{n.commission.subject}</span>}
                      {n.preview && n.kind === "followed_new_post" && <span className="text-zinc-500"> — {n.preview}</span>}
                      {n.event_title && !n.artwork?.title && <span>{n.other?.name ? " · " : ""}{n.event_title}{n.position ? ` · #${n.position}` : ""}</span>}
                      {n.preview && n.kind === "event_broadcast" && <span className="text-zinc-500"> — {n.preview}</span>}
                      {n.amount != null && <span className="ml-2 text-[#CCFF00] font-anton">${Number(n.amount).toLocaleString()}</span>}
                    </div>
                  </div>
                  <button onClick={(e) => { e.preventDefault(); del(n.id); }} className="text-zinc-500 hover:text-[#FF4D4D] p-1">
                    <Trash2 size={12} />
                  </button>
                </div>
              );
              return to ? <Link key={n.id} to={to} data-testid={`notif-${n.id}`}>{inner}</Link> : <div key={n.id} data-testid={`notif-${n.id}`}>{inner}</div>;
            })}
          </div>
        )}
    </div>
  );
}
