import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, fileUrl, ORIGIN } from "../api";
import { useCart } from "../context/CartContext";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export function Cart() {
  const { items, remove, total } = useCart();
  const [busy, setBusy] = useState(false);
  const checkout = async () => {
    if (items.length === 0) return;
    setBusy(true);
    try {
      const r = await api.post("/payments/checkout", { items: items.map((i) => ({ artwork_id: i.id, quantity: 1 })), origin_url: ORIGIN });
      window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Checkout failed"); setBusy(false); }
  };
  return (
    <div data-testid="cart-page" className="max-w-[1200px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Your selection</div>
      <h1 className="font-anton text-6xl md:text-8xl uppercase mt-4 mb-12">The Cart</h1>
      {items.length === 0 ? (
        <div className="border border-dashed border-white/10 py-24 text-center rounded-sm">
          <div className="label-caps text-zinc-500">Empty — for now.</div>
          <Link to="/explore" className="btn-lime mt-8 inline-flex">Explore Art</Link>
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-8">
          <div className="md:col-span-2 divide-y divide-white/8 border border-white/8 rounded-sm">
            {items.map((i) => (
              <div key={i.id} data-testid={`cart-item-${i.id}`} className="p-4 flex gap-4 items-center">
                <img src={resolveImg(i.image)} alt={i.title} className="w-24 h-24 object-cover rounded-sm" />
                <div className="flex-1 min-w-0">
                  <div className="font-unbounded font-semibold text-lg truncate">{i.title}</div>
                  <div className="label-caps mt-1">{i.artist}</div>
                </div>
                <div className="font-anton text-xl text-[#CCFF00]">${Number(i.price).toLocaleString()}</div>
                <button data-testid={`remove-${i.id}`} onClick={() => remove(i.id)} className="text-zinc-500 hover:text-[#FF4D4D] p-2"><Trash2 size={16} /></button>
              </div>
            ))}
          </div>
          <div className="md:col-span-1">
            <div className="glass-card p-6 sticky top-24 rounded-sm">
              <div className="label-caps">Total</div>
              <div className="font-anton text-5xl mt-2 text-[#CCFF00]" data-testid="cart-total">${Number(total).toLocaleString()}</div>
              <div className="text-xs text-zinc-500 mt-3">Shipping calculated at checkout.</div>
              <button data-testid="checkout-btn" onClick={checkout} disabled={busy} className="btn-lime w-full mt-6">
                {busy ? "Redirecting..." : "Secure Checkout"}
              </button>
              <div className="label-caps mt-4 text-zinc-600 text-center">Stripe · Test card 4242 4242 4242 4242</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function PaymentSuccess() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState("checking");
  const [tries, setTries] = useState(0);
  const [kind, setKind] = useState(null);
  const { clear } = useCart();
  const sid = params.get("session_id");

  useEffect(() => {
    if (!sid) { setStatus("error"); return; }
    let cancel = false;
    const poll = async () => {
      try {
        const r = await api.get(`/payments/status/${sid}`);
        if (cancel) return;
        setKind(r.data.kind);
        if (r.data.payment_status === "paid") { setStatus("paid"); clear(); return; }
        if (tries >= 15) { setStatus("timeout"); return; }
        setTimeout(() => setTries((t) => t + 1), 2000);
      } catch { setStatus("error"); }
    };
    poll();
    return () => { cancel = true; };
  }, [sid, tries]);

  return (
    <div data-testid="payment-success" className="max-w-2xl mx-auto px-6 pt-24 pb-32 text-center">
      {status === "checking" && <>
        <div className="label-caps text-[#7C3AED]">Confirming</div>
        <h1 className="font-anton text-6xl md:text-8xl uppercase mt-4">Hold tight...</h1>
      </>}
      {status === "paid" && <>
        <div className="label-caps text-[#CCFF00]">Confirmed</div>
        <h1 className="font-anton text-6xl md:text-8xl uppercase mt-4">
          {kind === "upload_fee" ? "Live now" :
           kind === "auction_win" ? "Piece is yours" :
           kind === "commission_payment" ? "Payment sent" :
           "Thank you."}
        </h1>
        <p className="text-zinc-400 mt-8">
          {kind === "upload_fee" ? "Your artwork is live in the marketplace." :
           kind === "auction_win" ? "Your auction win is settled. Art Core will coordinate delivery with the seller." :
           kind === "commission_payment" ? "Funds released to the artist. Enjoy your custom piece." :
           "A confirmation email is on its way. Art Core will coordinate shipping."}
        </p>
        <Link to={
          kind === "upload_fee" ? "/studio" :
          kind === "auction_win" ? "/orders" :
          kind === "commission_payment" ? "/commissions" :
          "/orders"
        } className="btn-lime mt-10 inline-flex">
          {kind === "upload_fee" ? "Back to Studio" :
           kind === "auction_win" ? "View Order" :
           kind === "commission_payment" ? "Back to Commissions" :
           "View Orders"}
        </Link>
      </>}
      {status === "timeout" && <>
        <h1 className="font-anton text-5xl uppercase mt-4">Still processing...</h1>
        <p className="text-zinc-400 mt-4">Check back shortly.</p>
      </>}
      {status === "error" && <h1 className="font-anton text-5xl uppercase">Something went sideways.</h1>}
    </div>
  );
}

export function PaymentCancel() {
  return (
    <div data-testid="payment-cancel" className="max-w-2xl mx-auto px-6 pt-24 pb-32 text-center">
      <div className="label-caps text-[#FF4D4D]">Cancelled</div>
      <h1 className="font-anton text-6xl md:text-8xl uppercase mt-4">No worries.</h1>
      <p className="text-zinc-400 mt-8">Your cart is still here whenever you're ready.</p>
      <Link to="/cart" className="btn-lime mt-10 inline-flex">Back to Cart</Link>
    </div>
  );
}
