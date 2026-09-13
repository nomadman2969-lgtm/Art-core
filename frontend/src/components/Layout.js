import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { useState, useEffect } from "react";
import { api } from "../api";
import { ShoppingBag, User2, Menu, X, Search, MessageSquare, Bell, Compass } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguagePicker } from "./LanguagePicker";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const { items } = useCart();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [unreadNotif, setUnreadNotif] = useState(0);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!user) return;
    const load = () => {
      api.get("/messages/unread-count").then((r) => setUnread(r.data.count)).catch(() => {});
      api.get("/notifications/unread-count").then((r) => setUnreadNotif(r.data.count)).catch(() => {});
    };
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [user]);

  const links = [
    { to: "/explore", label: t("nav.explore"), testid: "nav-explore" },
    { to: "/marketplace", label: t("nav.marketplace"), testid: "nav-marketplace" },
    { to: "/upcycle", label: t("nav.upcycle"), testid: "nav-upcycle" },
    { to: "/artists", label: t("nav.artists"), testid: "nav-artists" },
    { to: "/auctions", label: t("nav.auctions"), testid: "nav-auctions" },
    { to: "/rankings", label: t("nav.rankings"), testid: "nav-rankings" },
    { to: "/events", label: t("nav.events"), testid: "nav-events" },
  ];

  const submitSearch = (e) => {
    e.preventDefault();
    if (q.trim()) nav(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0C] text-white relative">
      <header className="sticky top-0 z-50 glass-nav">
        <div className="max-w-[1600px] mx-auto px-4 md:px-8 h-16 flex items-center gap-6">
          <Link to="/" data-testid="brand-link" className="font-anton text-2xl md:text-3xl uppercase tracking-tight flex items-center gap-1">
            Art<span className="text-[#CCFF00]">Core</span>
          </Link>

          <nav className="hidden lg:flex items-center gap-1">
            {links.map((l) => (
              <Link key={l.to} to={l.to} data-testid={l.testid}
                className="label-caps px-3 py-1.5 rounded text-zinc-400 hover:text-[#CCFF00] transition-colors relative">
                {l.label}
                {l.badge && <span className="ml-2 text-[9px] px-1.5 py-0.5 bg-[#7C3AED]/20 text-[#7C3AED] rounded">{l.badge}</span>}
              </Link>
            ))}
          </nav>

          <form onSubmit={submitSearch} className="hidden md:flex flex-1 max-w-md ml-auto">
            <div className="relative w-full">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input data-testid="nav-search" value={q} onChange={(e) => setQ(e.target.value)}
                placeholder={t("nav.search_placeholder")}
                className="w-full bg-white/[0.03] border border-white/10 pl-9 pr-4 py-2 text-sm outline-none focus:border-[#CCFF00] rounded-sm" />
            </div>
          </form>

          <div className="flex items-center gap-1 md:gap-3 ml-auto lg:ml-0">
            <LanguagePicker />
            <Link to="/cart" data-testid="nav-cart" className="relative p-2 hover:text-[#CCFF00] transition-colors">
              <ShoppingBag size={18} />
              {items.length > 0 && (
                <span data-testid="cart-count" className="absolute -top-1 -right-1 bg-[#CCFF00] text-black text-[10px] px-1 py-0 min-w-[16px] text-center font-bold rounded-sm">
                  {items.length}
                </span>
              )}
            </Link>
            {user && (
              <Link to="/messages" data-testid="nav-messages" className="relative p-2 hover:text-[#CCFF00] transition-colors">
                <MessageSquare size={18} />
                {unread > 0 && <span className="absolute -top-1 -right-1 bg-[#FF4D4D] text-white text-[10px] px-1 min-w-[16px] text-center font-bold rounded-sm">{unread}</span>}
              </Link>
            )}
            {user && (
              <Link to="/notifications" data-testid="nav-notifications" className="relative p-2 hover:text-[#CCFF00] transition-colors hidden md:block">
                <Bell size={18} />
                {unreadNotif > 0 && <span className="absolute -top-1 -right-1 bg-[#CCFF00] text-black text-[10px] px-1 min-w-[16px] text-center font-bold rounded-sm">{unreadNotif}</span>}
              </Link>
            )}
            {user ? (
              <div className="hidden md:flex items-center gap-3 ml-2">
                {user.role === "admin" && <Link to="/admin" data-testid="nav-admin" className="label-caps hover:text-[#CCFF00]">{t("nav.admin")}</Link>}
                {(user.role === "artist" || user.role === "admin") && <Link to="/studio" data-testid="nav-studio" className="label-caps hover:text-[#CCFF00]">{t("nav.studio")}</Link>}
                {(user.role === "artist" || user.role === "admin") && <Link to="/selling" data-testid="nav-selling" className="label-caps hover:text-[#CCFF00]">{t("nav.selling")}</Link>}
                {user.role === "buyer" && <Link to="/dashboard" data-testid="nav-dashboard" className="label-caps hover:text-[#CCFF00]">{t("nav.dashboard")}</Link>}
                <Link to="/orders" data-testid="nav-orders" className="label-caps hover:text-[#CCFF00]">{t("nav.orders")}</Link>
                <Link to="/tickets" data-testid="nav-tickets" className="label-caps hover:text-[#CCFF00]">{t("nav.tickets")}</Link>
                <Link to="/feed" data-testid="nav-feed" className="label-caps hover:text-[#CCFF00]">{t("nav.feed")}</Link>
                <Link to="/saved" data-testid="nav-saved" className="label-caps hover:text-[#CCFF00]">{t("nav.saved")}</Link>
                <Link to="/offers" data-testid="nav-offers" className="label-caps hover:text-[#CCFF00]">{t("nav.offers")}</Link>
                <Link to="/commissions" data-testid="nav-commissions" className="label-caps hover:text-[#CCFF00]">{t("nav.commissions")}</Link>
                <Link to="/security" data-testid="nav-security" className="label-caps hover:text-[#CCFF00]" title="Account security">{t("nav.security")}</Link>
                {user.role === "artist" && <Link to="/pro" data-testid="nav-pro" className={`label-caps ${user.pro_active ? "text-[#C4B5FD]" : "hover:text-[#CCFF00]"}`}>Pro</Link>}
                <button data-testid="logout-btn" onClick={() => { logout(); nav("/"); }} className="label-caps hover:text-[#FF4D4D]">{t("nav.logout")}</button>
              </div>
            ) : (
              <div className="hidden md:flex items-center gap-2 ml-2">
                <Link to="/login" data-testid="nav-login" className="label-caps px-3 py-1.5 hover:text-[#CCFF00]">{t("nav.sign_in")}</Link>
                <Link to="/register" data-testid="nav-register" className="btn-lime !py-2 !text-xs">{t("nav.join")}</Link>
              </div>
            )}
            <button className="lg:hidden p-2" onClick={() => setOpen(!open)} data-testid="mobile-menu-btn">
              {open ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        {open && (
          <div className="lg:hidden border-t border-white/5 bg-[#0A0A0C]">
            <div className="px-6 py-6 flex flex-col gap-4">
              {links.map((l) => <Link key={l.to} to={l.to} onClick={() => setOpen(false)} className="label-caps">{l.label} {l.badge && <span className="text-[#7C3AED] ml-2">· soon</span>}</Link>)}
              <form onSubmit={(e) => { submitSearch(e); setOpen(false); }} className="flex">
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("nav.search_short")} className="flex-1 bg-white/5 border border-white/10 px-3 py-2 text-sm rounded-sm" />
              </form>
              {user ? (
                <>
                  {user.role === "admin" && <Link to="/admin" onClick={() => setOpen(false)} className="label-caps">{t("nav.admin")}</Link>}
                  {(user.role === "artist" || user.role === "admin") && <Link to="/studio" onClick={() => setOpen(false)} className="label-caps">{t("nav.studio")}</Link>}
                  <Link to="/messages" onClick={() => setOpen(false)} className="label-caps">{t("nav.messages")}</Link>
                  <Link to="/security" onClick={() => setOpen(false)} className="label-caps">{t("nav.security")}</Link>
                  <button onClick={() => { logout(); setOpen(false); nav("/"); }} className="label-caps text-left text-[#FF4D4D]">{t("nav.logout")}</button>
                </>
              ) : (
                <>
                  <Link to="/login" onClick={() => setOpen(false)} className="label-caps">{t("nav.sign_in")}</Link>
                  <Link to="/register" onClick={() => setOpen(false)} className="btn-lime !py-2 !text-xs w-fit">{t("nav.join_full")}</Link>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      <main className="fade-up">{children}</main>

      <footer className="border-t border-white/5 mt-32">
        <div className="max-w-[1600px] mx-auto px-6 md:px-12 py-16 grid md:grid-cols-5 gap-12">
          <div className="md:col-span-2">
            <div className="font-anton text-4xl uppercase">Art<span className="text-[#CCFF00]">Core</span></div>
            <p className="text-zinc-500 text-sm mt-4 max-w-sm leading-relaxed">{t("footer.tagline")}</p>
          </div>
          <div>
            <div className="label-caps mb-4">{t("footer.discover")}</div>
            <ul className="space-y-2 text-sm text-zinc-300">
              <li><Link to="/explore">{t("nav.explore")}</Link></li>
              <li><Link to="/marketplace">{t("nav.marketplace")}</Link></li>
              <li><Link to="/artists">{t("nav.artists")}</Link></li>
              <li><Link to="/auctions">{t("nav.auctions")}</Link></li>
            </ul>
          </div>
          <div>
            <div className="label-caps mb-4">{t("footer.for_artists")}</div>
            <ul className="space-y-2 text-sm text-zinc-300">
              <li><Link to="/register?role=artist">{t("footer.sell_your_work")}</Link></li>
              <li><Link to="/studio">{t("nav.studio")}</Link></li>
              <li><Link to="/commissions">{t("nav.commissions")}</Link></li>
              <li><Link to="/rankings">{t("nav.rankings")}</Link></li>
            </ul>
          </div>
          <div>
            <div className="label-caps mb-4">{t("footer.newsletter")}</div>
            <NewsletterForm />
          </div>
        </div>
        <div className="border-t border-white/5 py-6 text-center text-xs text-zinc-500 font-unbounded">© {new Date().getFullYear()} Art Core — {t("footer.made_for_artists")}</div>
      </footer>
    </div>
  );
}

function NewsletterForm() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [ok, setOk] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/newsletter", { email });
      setOk(true); setEmail("");
    } catch {}
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <input data-testid="newsletter-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
        placeholder="you@studio.com"
        className="bg-white/[0.03] border border-white/10 rounded-sm py-2 px-3 text-sm outline-none focus:border-[#CCFF00]" />
      <button data-testid="newsletter-submit" className="btn-ghost self-start !py-2 !px-4 !text-xs">{t("footer.get_updates")}</button>
      {ok && <div data-testid="newsletter-ok" className="text-xs text-[#CCFF00]">{t("footer.on_the_list")}</div>}
    </form>
  );
}
