import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../api";
import { Bell, Gavel, Trophy, Palette, UserPlus, Check, Trash2, MessageSquare, Heart } from "lucide-react";

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
};

export default function Notifications() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

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
          <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4">Notifications</h1>
          <div className="label-caps text-zinc-500 mt-2">{unread} unread</div>
        </div>
        {unread > 0 && (
          <button data-testid="mark-all-read" onClick={markAll} className="btn-ghost !py-2 !text-xs">Mark all read</button>
        )}
      </div>

      {loading ? <div className="text-zinc-500 py-16 text-center label-caps">Loading...</div> :
        items.length === 0 ? (
          <div className="border border-dashed border-white/10 py-20 text-center rounded-sm">
            <div className="label-caps text-zinc-500">Nothing here yet.</div>
            <div className="text-sm text-zinc-400 mt-4">Bid on an auction, follow an artist, or request a commission — updates will land here.</div>
          </div>
        ) : (
          <div className="border border-white/8 divide-y divide-white/8 rounded-sm">
            {items.map((n) => {
              const meta = KIND_META[n.kind] || { label: n.kind, icon: <Bell size={14} />, color: "#A1A1AA" };
              const to = n.commission?.id ? `/commissions/${n.commission.id}` :
                         n.auction?.id ? `/auctions/${n.auction.id}` :
                         n.offer?.id ? "/offers" :
                         n.order?.id ? `/orders/${n.order.id}` :
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
