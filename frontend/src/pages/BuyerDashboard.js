import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "../api";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { Heart, ShoppingBag, Package } from "lucide-react";

const resolveImg = (p) => (p?.startsWith("http") ? p : fileUrl(p));

export default function BuyerDashboard() {
  const { user } = useAuth();
  const { items } = useCart();
  const [wishlist, setWishlist] = useState([]);

  useEffect(() => {
    // Wishlist = artworks user has liked
    (async () => {
      try {
        const feedR = await api.get("/feed?limit=200");
        const liked = feedR.data.filter((a) => a.liked);
        setWishlist(liked);
      } catch {}
    })();
  }, []);

  return (
    <div data-testid="buyer-dashboard" className="max-w-[1400px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00]">Collector</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4">Hey, {user?.name}.</h1>

      <div className="grid md:grid-cols-3 gap-4 mt-12">
        <StatBox label="Cart" value={items.length} icon={<ShoppingBag size={20} />} color="#CCFF00" />
        <StatBox label="Wishlist" value={wishlist.length} icon={<Heart size={20} />} color="#FF4D4D" />
        <StatBox label="Orders" value="—" icon={<Package size={20} />} color="#7C3AED" hint="Coming soon" />
      </div>

      <div className="mt-16">
        <div className="label-caps mb-6">Your Wishlist</div>
        {wishlist.length === 0 ? (
          <div className="border border-dashed border-white/10 py-16 text-center label-caps text-zinc-500 rounded-sm">
            Nothing saved yet. <Link to="/explore" className="text-[#CCFF00] ml-2">Explore →</Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {wishlist.map((a) => (
              <Link key={a.id} to={`/artwork/${a.id}`} data-testid={`wish-${a.id}`}
                className="block border border-white/8 hover-lift-card rounded-sm">
                <img src={resolveImg(a.images?.[0])} className="w-full aspect-square object-cover" alt="" />
                <div className="p-3">
                  <div className="font-unbounded text-sm truncate">{a.title}</div>
                  <div className="text-xs text-[#CCFF00] mt-1">${Number(a.price).toLocaleString()}</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value, icon, color, hint }) {
  return (
    <div className="glass-card p-6 rounded-sm">
      <div className="flex items-center gap-3">
        <div style={{ color }}>{icon}</div>
        <div className="label-caps">{label}</div>
      </div>
      <div className="font-anton text-5xl mt-4" style={{ color }}>{value}</div>
      {hint && <div className="label-caps mt-1 text-zinc-600">{hint}</div>}
    </div>
  );
}
