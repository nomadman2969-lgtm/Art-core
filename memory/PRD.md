# Art Core — PRD

## Original Problem Statement (Feb 2026)
A modern social marketplace exclusively for visual artists — combining Instagram, Facebook, Etsy, Behance, DeviantArt, and StockX. Feels like a billion-dollar startup: modern street art + graffiti + neon lighting + urban gallery + luxury minimalist UI + Apple-quality polish. Dark mode by default.

Evolved from "House of Monster" (initial MVP) — same repo, React + FastAPI + MongoDB stack.

## User Personas
- **Artists** — painters, illustrators, sculptors, graffiti artists, digital artists, photographers
- **Collectors / Buyers** — discover, favorite, purchase originals
- **Admin (Founder — Monster)** — curate features, moderate, set commission/fees

## Core Requirements (static)
- JWT auth with roles: buyer, artist, admin
- Artwork upload with images, physical dimensions, price
- Marketplace with filters (medium, price, sort)
- Explore feed (Instagram-like)
- Artist portfolio pages with follow/message
- Artwork detail with likes, comments, share
- Cart + Stripe Checkout for buyers
- Upload fee via Stripe for artists (configurable)
- Basic direct messaging between users
- Search across artworks + artists
- Admin dashboard: commission %, upload fee, currency, featured curation, AOTW (Featured Piece), orders, mentorship inbox
- Newsletter signup
- Dark, editorial, gallery-inspired UI

## Design System (current)
- Fonts: Anton (display) / Unbounded (secondary) / Manrope (body)
- Palette: #0A0A0C bg, #CCFF00 neon lime, #7C3AED violet, #FF4D4D coral
- Glassmorphism nav + cards, grain overlay on hero, marquee, bento grid explore
- Coming Soon pages treated as premium (auctions, commissions, events, rankings, notifications, studio themes)

## Implemented (Feb 10, 2026)

### Backend (FastAPI + MongoDB)
- Auth, artworks, payments, admin, artist dashboard (v1)
- Social layer: follows, likes, comments, feed
- Messages, search
- Auctions, rankings, commissions

- **Studio system (NEW)**: `/api/studio/themes`, `/api/studio/{artist_id}`, PATCH `/api/studio`, `/api/studio/analytics/me`, `POST /api/studio/ai-design` (Claude Sonnet 4.6)
- **Studio Posts (NEW)**: `/api/posts` CRUD + pin + like

### Frontend (React) — Live routes
- Home, Explore, Marketplace, Artwork detail, Artists list, Search
- Auth, Cart, Payment success/cancel
- Messages inbox + thread, Buyer dashboard
- Auctions list + detail + create
- Rankings leaderboard
- Commissions inbox + create + detail
- **Artist Studio** (`/artist/:id`): immersive themed page with header, follow/message/commission CTAs, live auction rails, artwork walls, social feed, story block, commission CTA
- **Studio Editor** (`/studio`): tabs for Overview, Theme & Look (7 themes, accent picker, lighting presets, AI designer), Sections (reorder/rename/toggle), My Story (bio, location, style, education, awards, socials), Posts (Facebook-style timeline), Artworks, Analytics (visits, likes, top artworks, revenue), Payouts
- Coming Soon: /events, /notifications, /studio-custom

### Testing
- Iteration 2: 54/54 (Core Art Core)
- Iteration 3: 42/42 (Auctions, Rankings, Commissions)
- Iteration 4: 35/35 (Studio + Posts + AI Designer)

### Frontend (React)
- Layout with glassy nav, search, cart badge, unread messages badge
- Home: hero, categories, trending bento, featured artists, promo blocks, testimonials, CTA
- Explore feed with likes
- Marketplace (filters + grid)
- Artwork detail: gallery, price, likes, comments, share, message artist
- Artist list + portfolio (avatar ring, follow/message, stats)
- Login / Register (buyer or artist)
- Cart + Payment Success/Cancel with Stripe polling
- Artist Studio (dashboard, connect stub, upload flow)
- Admin Command Desk (7 tabs)
- Buyer Dashboard (wishlist from liked artworks)
- Messages inbox + thread view (polling every 5s)
- Search results (artists + artworks)
- Coming Soon stubs: auctions, commissions, events, rankings, notifications, studio themes

### Testing (Iteration 2)
- 54/54 backend tests passed
- 2 minor Mongo ObjectId leaks (mentorship POST, comments POST) auto-fixed by testing agent

## Prioritized Backlog

### P0 — v1 polish
- Frontend E2E test pass (currently backend-only tested)
- Real photo uploads by the user (4 reference images pending)
- Real founder story content (currently placeholder)

### P1 — v2 features (currently stubbed as Coming Soon)
- Live auctions: real-time bidding, countdown, chat
- Commission system: request → accept/counter → track → deliver
- Events: geolocation, RSVP, ticketing
- Rankings/gamification: bronze → legendary, leaderboards, badges
- Real-time notifications feed
- Studio profile customization: themes, banners, widgets

### P2 — later
- Stripe Connect payouts (currently mocked flow)
- Resend email receipts
- 2FA (structure ready, not wired)
- Video posts / stories rail
- Digital prints / print-on-demand

## Communication System v2 (Feb 25, 2026 · pm)

### Messages (`messages.py` rewritten)
- **7 attachment kinds**: artwork · studio · image · commission · auction · offer · order — each enriched on send + fetch with title/price/image/status
- **Read receipts**: `read_at`, `delivered_at`; auto-mark-read on thread open; explicit `POST /thread/{id}/read`
- **Threads endpoint**: last message + unread count + `last_from_me` + `last_read` for correct Check/CheckCheck icons
- **Search**: `GET /messages/search?q=` full-text; `GET /threads?q=` filters by name or last message
- **Throttled DM notifications**: kind=new_message dedup per sender per hour

### Auction Ending Reminder
- New `_check_ending_soon` fires kind=auction_ending to current bidder + watchers when <1h remains (idempotent via `ending_soon_notified` flag)

### Frontend
- **Rewrote `/messages`** with avatar circles, Check/CheckCheck read icons, unread badges, debounced search
- **Rewrote thread page** with sticky header (studio link), 5-min timestamp grouping, Paperclip/Palette attachment buttons, pending-attachment preview + removal, `AttachmentCard` component for all 7 kinds
- **Notifications**: added new_message + auction_ending kinds with proper routing (new_message → /messages/{sender_id})

### Testing — 16/16 backend + 100% frontend, plus watchers-collection fix verified via self-test


### Backend (`social.py` major rewrite + `studio.py` post mentions)
- **Home feed**: `GET /api/feed/home` merges studio posts + new artworks from followed artists, sorted DESC, with per-item like/comment counts and liked flag
- **Threaded comments**: `parent_id` on comments, `GET /artworks/{id}/comments` returns top-level with `replies[]`, reply notifies parent author
- **@Mentions**: regex parser on comments + posts + post-comments, resolves handle → user, fires `mentioned_in_*` notifications
- **Shares**: `POST /artworks/{id}/share` increments count + throttled artist notification (once per user per day)
- **Saves + Collections**: full CRUD (`POST/GET/DELETE /collections`), "All Saved" pseudo-collection, save with optional `collection_id`, artwork covers precomputed
- **Post engagement**: like/unlike posts, comment on posts, all with notifications
- **Followers/Following lists**: `GET /users/{id}/followers` and `/following`

### Frontend
- **NEW `/feed`**: HomeFeed page — mixed timeline of `PostCard` + `ArtworkFeedCard` with optimistic like/save/share, kind badges (WIP, sold, exhibition...), TimeAgo, @mention highlighting
- **NEW `/saved`**: SavedIndex + CollectionDetail — grid of collections with cover mosaic, New Collection modal, private toggle, unsave from detail
- **ArtworkDetail**: Save button + Share button (fires API), reply-to-comment with inline input, threaded rendering with left border, @mentions styled in accent
- **Notifications**: 9 new social kinds with proper labels/icons, click-through routing for artworks/posts, fixed concatenation bug (title · user separator)

### Testing — 19/19 backend + 100% frontend at both desktop & mobile


### Studio Starter Templates
- 4 curated one-tap layouts: **Emerging Artist**, **Gallery Owner**, **Print Shop**, **Dark Solo Show**
- `GET /api/studio/templates` + `POST /api/studio/apply-template` (applies to draft, unique section IDs)

### True Drag-Drop Sections
- HTML5 native drag-drop (up/down arrows kept as fallback)
- Visual feedback + typing-safe (title input stops drag propagation)

### Admin Refund Console
- Refunds tab in `/admin` with one-click full/partial refunds for orders + commissions
- Uses `stripe.Refund.create(reverse_transfer=True, refund_application_fee=True)` — Stripe Connect auto-reverses artist payouts + platform commission
- Manually-released payouts marked `clawback_needed`; sold artworks auto-relist on full refund
- Notifications fired to all parties (order_refunded / payout_reversed / commission_refunded)

### Testing — 10/10 backend + 100% frontend, zero regressions



### Studio Signature Feature
- **7 themes** aligned to spec: Urban Graffiti · Luxury Gallery · Dark Gallery · Industrial · Neon Digital · Minimal · Custom (with legacy alias migration)
- **6 textures** rendered as SVG data-URI overlays: Graffiti / Brick / Concrete / Neon Grid / Grain / Paper — with intensity slider
- **12 section kinds** including 4 new rich blocks: `announcement` (info/success/warning), `text_block`, `button_cta` (label + link), `image_block` (upload + caption)
- **5 gallery layouts** per section: Grid, Masonry (CSS columns), Salon Wall (asymmetric), Single Showcase (thumbnail nav), Carousel (3-at-a-time)
- **Featured artwork picker** — multi-select up to 12 pieces in exact order
- **Commission availability toggle** with custom blurb (closed state renders "Commissions currently closed")
- **Draft → Preview → Publish workflow** — all edits go to draft; preview via `/artist/{id}?preview=1` with sticky orange banner; Publish flips draft → live atomically

### Commission Escrow Timeline UI
- Added `CommissionTimeline` on `/commissions/{id}` — 7-stage vertical timeline (request → response → deposit → progress → delivered → approved → paid), computed from `progress[]` history
- Escrow allocation bar showing deposit vs balance status
- Color coded: green (done), orange (pending), red (declined/failed)

### Stripe Connect Express (real artist payouts)
- New `/api/connect/onboarding-link`, `/status`, `/dashboard-link` endpoints (module `connect.py`)
- `build_transfer_options(seller_id, gross)` helper wired into auction/offer/commission checkouts — attaches `transfer_data.destination` + `application_fee_amount` when seller has active connected account
- `transfer_manual` helper — orders.mark_delivered now attempts a real Stripe Transfer when payout wasn't auto-routed at checkout
- Graceful fallback: sellers without Connect still get orders/notifications; funds land on platform (existing behavior)
- Payouts panel in Studio Editor rewritten with real Connect status + Stripe Express dashboard link

### Testing
- 23/23 new tests + 13/13 regression tests passed via testing agent
- Testing agent fixed one P0 useEffect Promise bug on CommissionDetail (git committed)


Full commerce system audit + upgrade:

### Offers (make-an-offer) — NEW module (`offers.py`)
- Buyer offers on live artworks (50–100% of list price)
- Seller accept / decline / counter (>original, ≤list)
- Buyer accept-counter / decline-counter / withdraw
- Stripe payment for accepted offers (`/api/payments/offers/{id}/pay`)
- Auto-expires competing offers when one is paid
- Full notifications chain

### Auction hardening
- Scheduled auctions with `start_at` (auto-activates on time)
- Atomic compare-and-swap on bids using `find_one_and_update` with `current_bid` + `end_at` + `status` match filters — prevents concurrent-bid race conditions (returns 409 to loser)
- eBay-style proxy bidding: top ceiling jumps directly to `second_highest_ceiling + 1` in ONE atomic bid (previously stepped +1 up to 30 iterations, capped at ~30)
- Watchers notified on leader change and 6h before payment deadline
- 48-hour payment window with next-bidder forfeit chain

### Order fulfillment
- `POST /api/orders/{id}/ship` (seller, requires carrier+tracking)
- `POST /api/orders/{id}/mark-delivered` (buyer, releases payouts)
- `GET /api/orders/selling` for artist fulfillment queue
- fulfillment status pipeline: pending → shipped → delivered
- Reviews gated behind delivered status

### Frontend
- `/offers` inbox (buyer & seller tabs) at `pages/Offers.js`
- Make-an-Offer modal on `ArtworkDetail`
- Fulfillment panel on `OrderDetail` (ship form + mark-delivered CTA)
- `/orders` and `/selling` routes in nav
- Scheduled tab + start_at picker on Auctions
- Countdown works for both start_at and end_at

### Testing
- 13/13 pytest suite `tests/test_commerce_full.py` passing
- Covers race conditions, idempotency, offer lifecycle, proxy pricing, fulfillment, commissions

