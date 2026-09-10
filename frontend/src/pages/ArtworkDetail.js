import { useTranslation } from "react-i18next";
import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api, fileUrl } from "../api";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { ReportButton } from "../components/ReportButton";
import { BeforeAfter } from "./Upcycle";
import { toast } from "sonner";
import { Share2, Heart, MessageCircle, Send, Tag, X, Bookmark } from "lucide-react";
import MentionInput from "../components/MentionInput";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export default function ArtworkDetail() {
  const { t } = useTranslation();
  const { id } = useParams();
  const [art, setArt] = useState(null);
  const [idx, setIdx] = useState(0);
  const [likes, setLikes] = useState({ count: 0, liked: false });
  const [comments, setComments] = useState([]);
  const [comment, setComment] = useState("");
  const [replyingTo, setReplyingTo] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [saved, setSaved] = useState(false);
  const { add, items } = useCart();
  const { user } = useAuth();
  const nav = useNavigate();
  const [showOffer, setShowOffer] = useState(false);
  const [offerAmt, setOfferAmt] = useState("");
  const [offerMsg, setOfferMsg] = useState("");
  const [offerBusy, setOfferBusy] = useState(false);

  const submitOffer = async (e) => {
    e.preventDefault();
    if (!user) { toast(t("artwork.sign_in_offer")); return; }
    setOfferBusy(true);
    try {
      await api.post("/offers", { artwork_id: id, amount: Number(offerAmt), message: offerMsg || undefined });
      toast.success("Offer sent");
      setShowOffer(false); setOfferAmt(""); setOfferMsg("");
      nav("/offers");
    } catch (er) { toast.error(er?.response?.data?.detail || "Offer failed"); }
    setOfferBusy(false);
  };

  const loadAll = () => {
    api.get(`/artworks/${id}`).then((r) => setArt(r.data)).catch(() => nav("/marketplace"));
    api.get(`/artworks/${id}/likes`).then((r) => setLikes(r.data));
    api.get(`/artworks/${id}/comments`).then((r) => setComments(r.data));
    if (user) api.get(`/artworks/${id}/saved`).then((r) => setSaved(r.data.saved)).catch(() => {});
  };
  useEffect(loadAll, [id]);

  if (!art) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  const inCart = items.some((i) => i.id === art.id);
  const isSold = art.status === "sold";

  const share = async () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/share/artwork/${id}`;
    if (navigator.share) { try { await navigator.share({ title: art.title, url }); } catch {} }
    else { try { await navigator.clipboard.writeText(url); } catch {} toast.success("Link copied"); }
    try { await api.post(`/artworks/${id}/share`, { target: navigator.share ? "native" : "copy_link" }); } catch {}
  };
  const toggleSave = async () => {
    if (!user) { toast("Sign in to save"); return; }
    try {
      if (saved) { await api.delete(`/artworks/${id}/save`); setSaved(false); toast("Removed from saved"); }
      else { await api.post(`/artworks/${id}/save`, {}); setSaved(true); toast.success("Saved to your library"); }
    } catch { toast.error("Failed"); }
  };
  const toggleLike = async () => {
    if (!user) { toast("Sign in to like"); return; }
    try {
      if (likes.liked) { await api.delete(`/artworks/${id}/like`); setLikes({ liked: false, count: likes.count - 1 }); }
      else { await api.post(`/artworks/${id}/like`); setLikes({ liked: true, count: likes.count + 1 }); }
    } catch { toast.error("Try again"); }
  };
  const postComment = async (e, parentId = null, text = null) => {
    if (e) e.preventDefault();
    if (!user) { toast("Sign in to comment"); return; }
    const body = text ?? comment;
    if (!body.trim()) return;
    try {
      await api.post(`/artworks/${id}/comments`, { text: body, parent_id: parentId });
      if (parentId) { setReplyText(""); setReplyingTo(null); }
      else setComment("");
      const r = await api.get(`/artworks/${id}/comments`);
      setComments(r.data);
    } catch { toast.error("Failed"); }
  };

  const renderCommentText = (text) => {
    if (!text) return null;
    return text.split(/(@[a-zA-Z0-9_\-\.]{2,32})/g).map((p, i) =>
      p.startsWith("@") ? <span key={i} className="text-[#CCFF00]">{p}</span> : <span key={i}>{p}</span>
    );
  };
  const submitAotw = async () => {
    try { await api.post(`/artworks/${id}/submit-aotw`); toast.success("Submitted for Feature"); }
    catch { toast.error("Couldn't submit"); }
  };

  return (
    <div data-testid="artwork-detail" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-12 pb-32">
      <div className="grid md:grid-cols-12 gap-10">
        <div className="md:col-span-7">
          <div className="aspect-[4/5] bg-black overflow-hidden border border-white/8 rounded-sm">
            {art.section === "upcycle" && art.before_image && idx === 0
              ? <BeforeAfter before={art.before_image} after={art.images[0]} title={art.title} className="!object-contain" />
              : <img src={resolveImg(art.images[idx])} alt={art.title} className="w-full h-full object-contain" />}
          </div>
          {art.images.length > 1 && (
            <div className="grid grid-cols-6 gap-2 mt-3">
              {art.images.map((im, i) => (
                <button key={i} data-testid={`thumb-${i}`} onClick={() => setIdx(i)}
                  className={`aspect-square overflow-hidden border rounded-sm ${i === idx ? "border-[#CCFF00]" : "border-white/10"}`}>
                  <img src={resolveImg(im)} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="md:col-span-5 md:sticky md:top-24 self-start">
          <div className="label-caps flex items-center gap-2 flex-wrap">{art.medium}{art.style && art.style !== "upcycle" ? ` · ${art.style}` : ""}
            {art.delivery?.includes("local_pickup") && <span data-testid="pickup-badge" className="label-caps text-[10px] px-2 py-1 rounded-sm bg-[#34D399]/15 text-[#34D399]">Local pickup{art.location?.city ? ` · ${art.location.city}` : ""}</span>}
            {art.section === "upcycle" && <Link to="/upcycle" data-testid="upcycle-badge" className="label-caps text-[10px] px-2 py-1 rounded-sm bg-[#34D399]/20 text-[#34D399] hover:bg-[#34D399]/30">Upcycle · {art.furniture_type || "furniture"}</Link>}
          </div>
          <h1 className="font-anton text-5xl md:text-6xl uppercase mt-3 leading-[0.95]">{art.title}</h1>
          <div className="mt-4 flex items-center gap-3">
            <Link to={`/artist/${art.artist?.id}`} data-testid="link-artist" className="font-unbounded text-sm text-[#CCFF00] hover:underline">by {art.artist?.name}</Link>
          </div>
          <div className="mt-8 font-anton text-4xl text-[#CCFF00]">${Number(art.price).toLocaleString()}</div>
          <div className="mt-2 text-sm text-zinc-500">{art.width_in} × {art.height_in} in · {art.medium}{art.materials ? ` · ${art.materials}` : ""}</div>

          <div className="flex flex-wrap gap-3 mt-8">
            {isSold ? (
              <div data-testid="sold-badge" className="badge-coral !px-4 !py-2">{t("artwork.sold")}</div>
            ) : inCart ? (
              <button data-testid="in-cart" onClick={() => nav("/cart")} className="btn-lime">{t("artwork.in_cart")}</button>
            ) : (
              <button data-testid="add-to-cart" onClick={() => { add(art); toast.success(t("artwork.added")); }} className="btn-lime">{t("artwork.add_to_cart")}</button>
            )}
            {!isSold && user && art.artist?.id !== user.id && (
              <button data-testid="make-offer-btn" onClick={() => { if (!user) { toast(t("artwork.sign_in_offer")); return; } setShowOffer(true); }} className="btn-violet">
                <Tag size={14} className="mr-2" /> {t("artwork.make_offer")}
              </button>
            )}
            <button data-testid="like-btn" onClick={toggleLike} className="btn-ghost">
              <Heart size={14} className="mr-2" fill={likes.liked ? "#FF4D4D" : "none"} color={likes.liked ? "#FF4D4D" : undefined} />
              <span>{likes.count}</span>
            </button>
            <button data-testid="share-btn" onClick={share} className="btn-ghost"><Share2 size={14} className="mr-2" /> {t("artwork.share")}</button>
            <ReportButton targetType="artwork" targetId={art.id} ownerId={art.artist?.id} />
            <button data-testid="save-btn" onClick={toggleSave} className="btn-ghost">
              <Bookmark size={14} className="mr-2" fill={saved ? "#CCFF00" : "none"} color={saved ? "#CCFF00" : undefined} />
              {saved ? t("artwork.saved") : t("artwork.save")}
            </button>
            {user && art.artist?.id && user.id !== art.artist.id && (
              <Link to={`/messages/${art.artist.id}`} data-testid="msg-artist" className="btn-ghost"><MessageCircle size={14} className="mr-2" /> {t("artwork.message")}</Link>
            )}
            {user && (user.id === art.artist_id || user.role === "admin") && art.status === "live" && !art.aotw_submitted && (
              <button data-testid="submit-aotw" onClick={submitAotw} className="btn-violet">Submit AOTW</button>
            )}
          </div>

          {showOffer && (
            <div data-testid="offer-modal" className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setShowOffer(false)}>
              <div className="glass-card p-6 md:p-8 max-w-md w-full rounded-sm" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <div className="label-caps text-[#7C3AED]">Make an Offer</div>
                    <div className="font-anton text-3xl mt-2">{art.title}</div>
                    <div className="text-sm text-zinc-500 mt-1">List price ${Number(art.price).toLocaleString()}</div>
                  </div>
                  <button onClick={() => setShowOffer(false)} className="text-zinc-500 hover:text-white"><X size={20} /></button>
                </div>
                <form onSubmit={submitOffer} className="space-y-4">
                  <div>
                    <div className="label-caps mb-2">Your offer (USD)</div>
                    <input data-testid="offer-amount-input" type="number" required step="1"
                      min={Math.round(art.price * 0.5)} max={art.price}
                      value={offerAmt} onChange={(e) => setOfferAmt(e.target.value)}
                      placeholder={`$${Math.round(art.price * 0.5)}–$${art.price}`}
                      className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none focus:border-[#7C3AED] font-unbounded" />
                    <div className="text-xs text-zinc-500 mt-2">Offers must be at least 50% of list price.</div>
                  </div>
                  <div>
                    <div className="label-caps mb-2">Message (optional)</div>
                    <textarea data-testid="offer-message-input" rows={3} value={offerMsg} onChange={(e) => setOfferMsg(e.target.value)}
                      placeholder="Anything you want the artist to know..."
                      className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-2 outline-none focus:border-[#7C3AED]" />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button data-testid="offer-submit" disabled={offerBusy || !offerAmt} className="btn-lime flex-1">
                      {offerBusy ? "Sending..." : "Send Offer"}
                    </button>
                    <button type="button" onClick={() => setShowOffer(false)} className="btn-ghost">Cancel</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          <div className="mt-10 pt-8 border-t border-white/8">
            <div className="label-caps mb-4">About the piece</div>
            <p className="text-zinc-300 leading-relaxed whitespace-pre-wrap">{art.description}</p>
          </div>

          <div id="comments" className="mt-10 pt-8 border-t border-white/8">
            <div className="label-caps mb-4">Comments ({comments.reduce((n, c) => n + 1 + (c.replies?.length || 0), 0)})</div>
            <form onSubmit={postComment} className="flex gap-2 mb-6">
              <MentionInput testId="comment-input" value={comment} onChange={setComment}
                placeholder={user ? "Add a comment... (type @ to tag)" : "Sign in to comment"} disabled={!user}
                className="flex-1 bg-transparent border border-white/12 px-3 py-2 text-sm outline-none focus:border-[#CCFF00] rounded-sm w-full" />
              <button data-testid="comment-submit" disabled={!user || !comment.trim()} className="btn-lime !py-2"><Send size={14} /></button>
            </form>
            <div className="space-y-5 max-h-[500px] overflow-y-auto">
              {comments.map((c) => (
                <div key={c.id} data-testid={`comment-${c.id}`} className="border-b border-white/5 pb-3">
                  <div className="flex items-baseline justify-between">
                    <Link to={c.user_id ? `/artist/${c.user_id}` : "#"} className="font-unbounded text-sm font-semibold hover:text-[#CCFF00]">{c.user_name}</Link>
                    <div className="text-xs text-zinc-500">{new Date(c.created_at).toLocaleDateString()}</div>
                  </div>
                  <div className="text-sm text-zinc-300 mt-1 whitespace-pre-wrap">{renderCommentText(c.text)}</div>
                  {user && (
                    <button data-testid={`reply-btn-${c.id}`} onClick={() => setReplyingTo(replyingTo === c.id ? null : c.id)}
                      className="label-caps text-xs text-zinc-500 hover:text-[#CCFF00] mt-2">
                      {replyingTo === c.id ? "Cancel" : "Reply"}
                    </button>
                  )}
                  {replyingTo === c.id && (
                    <form onSubmit={(e) => postComment(e, c.id, replyText)} className="flex gap-2 mt-3 ml-4">
                      <MentionInput testId={`reply-input-${c.id}`} value={replyText} onChange={setReplyText} autoFocus
                        placeholder={`Reply to ${c.user_name}... (type @ to tag)`}
                        className="flex-1 bg-transparent border border-white/12 px-3 py-2 text-sm outline-none focus:border-[#CCFF00] rounded-sm w-full" />
                      <button data-testid={`reply-submit-${c.id}`} disabled={!replyText.trim()} className="btn-lime !py-2 !text-xs"><Send size={12} /></button>
                    </form>
                  )}
                  {c.replies && c.replies.length > 0 && (
                    <div className="mt-4 ml-6 pl-4 border-l border-white/8 space-y-3">
                      {c.replies.map((r) => (
                        <div key={r.id} data-testid={`reply-${r.id}`}>
                          <div className="flex items-baseline justify-between">
                            <Link to={r.user_id ? `/artist/${r.user_id}` : "#"} className="font-unbounded text-sm font-semibold hover:text-[#CCFF00]">{r.user_name}</Link>
                            <div className="text-xs text-zinc-500">{new Date(r.created_at).toLocaleDateString()}</div>
                          </div>
                          <div className="text-sm text-zinc-300 mt-1 whitespace-pre-wrap">{renderCommentText(r.text)}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {comments.length === 0 && <div className="text-zinc-500 text-sm">No comments yet.</div>}
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-white/8 text-xs text-zinc-500">
            Shipping coordinated by Art Core after purchase. Physical delivery for originals.
          </div>
        </div>
      </div>
    </div>
  );
}
