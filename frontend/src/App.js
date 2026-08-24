import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { CartProvider } from "@/context/CartContext";
import { Toaster } from "sonner";
import { Gavel, Palette, MapPin, Trophy, Bell, Sparkles } from "lucide-react";
import Layout from "@/components/Layout";
import Home from "@/pages/Home";
import Explore from "@/pages/Explore";
import Marketplace from "@/pages/Gallery";
import ArtworkDetail from "@/pages/ArtworkDetail";
import { ArtistsList } from "@/pages/Artists";
import { ArtistStudioPage } from "@/pages/ArtistStudio";
import { StudioEditor } from "@/pages/StudioEditor";
import { Login, Register } from "@/pages/Auth";
import { Cart, PaymentSuccess, PaymentCancel } from "@/pages/Cart";
import { UploadArtwork } from "@/pages/Artist";
import AdminDashboard from "@/pages/Admin";
import BuyerDashboard from "@/pages/BuyerDashboard";
import { MessagesInbox, MessageThread } from "@/pages/Messages";
import Search from "@/pages/Search";
import ComingSoon from "@/pages/ComingSoon";
import { AuctionsList, AuctionDetail, CreateAuction } from "@/pages/Auctions";
import Rankings from "@/pages/Rankings";
import { CommissionsInbox, CommissionCreate, CommissionDetail } from "@/pages/Commissions";
import OffersInbox from "@/pages/Offers";
import HomeFeed from "@/pages/HomeFeed";
import { SavedIndex, CollectionDetail } from "@/pages/Saved";
import { Orders, OrderDetail, SellingOrders } from "@/pages/Orders";
import Notifications from "@/pages/Notifications";
import NotFound from "@/pages/NotFound";
import ErrorBoundary from "@/components/ErrorBoundary";

function RequireRole({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="py-32 text-center label-caps text-zinc-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <BrowserRouter>
          <AuthProvider>
            <CartProvider>
              <Toaster theme="dark" position="top-center"
                toastOptions={{ style: { background: "#121214", color: "#FFFFFF", border: "1px solid rgba(255,255,255,0.1)", fontFamily: "Manrope" } }} />
              <Layout>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/explore" element={<Explore />} />
                <Route path="/marketplace" element={<Marketplace />} />
                <Route path="/artwork/:id" element={<ArtworkDetail />} />
                <Route path="/artists" element={<ArtistsList />} />
                <Route path="/artist/:id" element={<ArtistStudioPage />} />
                <Route path="/search" element={<Search />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/cart" element={<Cart />} />
                <Route path="/payment/success" element={<PaymentSuccess />} />
                <Route path="/payment/cancel" element={<PaymentCancel />} />
                <Route path="/messages" element={<RequireAuth><MessagesInbox /></RequireAuth>} />
                <Route path="/messages/:userId" element={<RequireAuth><MessageThread /></RequireAuth>} />
                <Route path="/dashboard" element={<RequireAuth><BuyerDashboard /></RequireAuth>} />
                <Route path="/studio" element={<RequireRole roles={["artist", "admin"]}><StudioEditor /></RequireRole>} />
                <Route path="/studio/upload" element={<RequireRole roles={["artist", "admin"]}><UploadArtwork /></RequireRole>} />
                <Route path="/admin" element={<RequireRole roles={["admin"]}><AdminDashboard /></RequireRole>} />

                {/* Coming soon stubs */}
                <Route path="/auctions" element={<AuctionsList />} />
                <Route path="/auctions/new" element={<RequireRole roles={["artist", "admin"]}><CreateAuction /></RequireRole>} />
                <Route path="/auctions/:id" element={<AuctionDetail />} />
                <Route path="/rankings" element={<Rankings />} />
                <Route path="/commissions" element={<RequireAuth><CommissionsInbox /></RequireAuth>} />
                <Route path="/commissions/new/:artistId" element={<RequireAuth><CommissionCreate /></RequireAuth>} />
                <Route path="/commissions/:id" element={<RequireAuth><CommissionDetail /></RequireAuth>} />
                <Route path="/offers" element={<RequireAuth><OffersInbox /></RequireAuth>} />
                <Route path="/feed" element={<RequireAuth><HomeFeed /></RequireAuth>} />
                <Route path="/saved" element={<RequireAuth><SavedIndex /></RequireAuth>} />
                <Route path="/saved/:id" element={<RequireAuth><CollectionDetail /></RequireAuth>} />
                <Route path="/orders" element={<RequireAuth><Orders /></RequireAuth>} />
                <Route path="/orders/:id" element={<RequireAuth><OrderDetail /></RequireAuth>} />
                <Route path="/selling" element={<RequireRole roles={["artist", "admin"]}><SellingOrders /></RequireRole>} />
                <Route path="/events" element={<ComingSoon title="Events" accent="#FF4D4D"
                  tagline="Openings, festivals, pop-ups — near you."
                  description="Discover gallery openings, art festivals, street fairs, pop-up markets, live painting events, and meetups near you. RSVP, buy tickets, save events."
                  icon={<MapPin size={20} className="text-[#FF4D4D]" />} />} />
                <Route path="/notifications" element={<RequireAuth><Notifications /></RequireAuth>} />
                <Route path="/studio-custom" element={<ComingSoon title="Studio Themes" accent="#CCFF00"
                  tagline="Make your profile yours."
                  description="Custom themes, backgrounds, gallery layouts, fonts, animated banners, widgets, pinned artwork, and profile music. Build your creative identity."
                  icon={<Sparkles size={20} className="text-[#CCFF00]" />} />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Layout>
          </CartProvider>
        </AuthProvider>
      </BrowserRouter>
      </ErrorBoundary>
    </div>
  );
}

export default App;
