# ART CORE — Master Build Prompt

> Paste this entire document into any AI app builder. It describes the complete product, business rules, data model, and design system of Art Core as built. Where a decision was made, it is stated as a requirement — do not re-litigate it.

---

## 0. One-paragraph brief

Build **Art Core**: a dark, editorial, mobile-first social marketplace exclusively for visual artists — Instagram × Etsy × Behance × StockX × an urban gallery. Artists get a customizable **Virtual Studio** (their own themed storefront/profile), sell originals with **escrow-style payouts released only after delivery is confirmed**, run **live auctions**, take **commissions**, flip furniture in an **Upcycle** section, and **host ticketed events** with QR check-in. Buyers browse, follow, save, make offers, bid, buy, and attend. The platform takes a **4% commission** (seller also pays card processing), sells an **Art Core Pro** subscription, and gives early "Founding Artists" a lifetime rate lock. Stack as built: React 18 (CRA + Tailwind + shadcn/ui) · FastAPI (Python 3.11, async) · MongoDB (Motor) · Stripe · Resend · EasyPost · Web Push · WebSockets.

---

## 1. Personas & roles

| Role | Can do |
|---|---|
| **buyer** (Collector) | Browse, like, save to collections, follow, comment, DM, make offers, bid, buy, request commissions, RSVP/buy tickets, review, dispute, confirm delivery |
| **artist** | Everything a buyer can + upload artworks (art or upcycle), customize Studio, post to feed, run auctions, accept commissions, host events, ship orders with tracking, receive payouts via Stripe Connect, view analytics, subscribe to Pro |
| **admin** (Founder) | Everything + Command Desk: fees, Stripe keys, featured curation, staff picks, refunds, disputes, reports/moderation, waivers, founding backfill |

Auth: email + password (bcrypt), JWT bearer (30-day), optional **2FA** (TOTP authenticator or email OTP, 8 recovery codes, 30-day trusted devices), rate-limited login. Roles fixed at signup (buyer or artist); admin seeded from env.

---

## 2. Design system (non-negotiable look)

- **Mood:** modern street art + graffiti + neon + luxury gallery minimalism. Dark mode only. Apple-level polish, zero "AI slop" (no purple-on-white gradients, no centered card grids everywhere).
- **Palette:** background `#0A0A0C`, surfaces `#111113`/`#121214`, neon lime accent `#CCFF00`, violet `#7C3AED`, coral red `#FF4D4D`, amber `#F5A623`, cyan `#00E5FF`, zinc greys for text.
- **Type:** `Anton` (display, uppercase, tight leading), `Unbounded` (secondary/labels), `Manrope` (body). Utility class `label-caps` = 10–11px uppercase tracking-widest zinc-500.
- **Components:** glassmorphism nav + cards (12–24px backdrop blur, 1px white/8 borders), grain overlay on hero, marquee strips, bento/masonry grids, pill/sharp-edged buttons (`btn-lime`, `btn-violet`, `btn-ghost`), rounded-sm (2px) corners, staggered fade-up entrance animations, lucide-react icons only (no emoji icons).
- **Layout:** left-aligned/asymmetric, generous spacing, max-width containers 3xl for reading pages, 1600px for grids. Fully responsive; verified at 390px.
- **Toasts:** sonner, dark theme, top-center.

---

## 3. Information architecture (routes)

Public: `/` Home · `/explore` (Instagram-style feed) · `/marketplace` (filters: medium, price, sort; Pro artists boosted) · `/upcycle` (furniture flips, before/after toggle, local-pickup map filter, "Flip my furniture" CTA) · `/artwork/:id` · `/artists` · `/artist/:id` (Virtual Studio) · `/host/:id` (event host page) · `/search` · `/auctions`, `/auctions/:id` · `/rankings` · `/events`, `/events/:id` · `/gift/:token` (public gift ticket) · `/pro` · `/legal/terms|privacy|refunds` · `/login`, `/register`

Authenticated: `/feed` (home timeline of followed artists) · `/saved`, `/saved/:id` (collections) · `/cart`, `/payment/success|cancel` · `/messages`, `/messages/:userId` · `/notifications` · `/offers` · `/orders`, `/orders/:id` · `/selling` (artist fulfillment queue) · `/tickets` (wallet) · `/commissions`, `/commissions/new/:artistId`, `/commissions/:id` · `/dashboard` (buyer) · `/studio` (artist Studio Editor) · `/studio/upload` · `/onboarding` (new artist, 3 steps) · `/auctions/new` · `/security` (2FA) · `/admin`

Global chrome: glass navbar (search, cart badge, unread DM badge, notification bell, language picker, Pro link), footer with Terms/Privacy/Refunds, **un-dismissable Delivery Confirmation modal** (see §6.4) mounted app-wide, PWA installable with service worker + push.

---

## 4. Core modules & business rules

### 4.1 Artworks
Fields: title, description, medium, dimensions (w/h/d + unit), year, edition, price, images[] (object storage, thumbnails via `?w=240|480|960`), status `draft|live|sold|removed`, `section: art|upcycle`, upcycle-only: `furniture_type` (chair/table/dresser/cabinet/lamp/mirror/shelf/bench/other), `materials`, `before_image`, `delivery: ['ships','local_pickup']`, `location {lat,lng,city}`. Optional per-listing upload fee (admin-configurable, default $0–5) paid via Stripe before going live. Views tracked for analytics. Likes, threaded comments with @mentions, shares (counted + notify), saves into named collections (private toggle).

### 4.2 Virtual Studio (artist profile as a themed micro-site)
- 7 themes: Urban Graffiti · Luxury Gallery · Dark Gallery · Industrial · Neon Digital · Minimal · Custom. **Luxury Gallery, Neon Digital, Custom are Pro-only (402 when not Pro).**
- Accent color picker, lighting presets, 6 SVG textures (graffiti/brick/concrete/neon grid/grain/paper) with intensity slider, cover/avatar.
- 12 section kinds, drag-and-drop ordering, rename/toggle: hero, featured artworks (pick ≤12 in order), gallery (5 layouts: grid, masonry, salon wall, single showcase, carousel), live auctions rail, posts timeline, story/bio block, commission CTA (with open/closed toggle + blurb), announcement, text block, button CTA, image block, events.
- 4 one-tap starter templates (Emerging Artist, Gallery Owner, Print Shop, Dark Solo Show).
- **Draft → Preview (`?preview=1`) → Publish** workflow; edits never go live until Publish.
- **AI Studio Designer:** describe a vibe → LLM (Claude Sonnet) returns theme/accent/texture/section config applied to draft.
- Header shows Founding badge, Pro badge, achievement badges (first_sale, ten_sales, auction_closer, commissioned, event_host, sold_out_show, rising, hundred_club, five_star), follower count, Follow / Message / Commission buttons, share (OG card), report.
- Analytics tab: studio visits (14d series), artwork views, saves, follower growth (8 wk), top viewed, revenue.

### 4.3 Social layer
Follows; home feed merges studio posts + new artworks from followed artists; posts have kinds (WIP, sold, exhibition, auction, …) with image OR video, @mentions, likes, comments; post composer (artists only) with 3 entry points on `/feed`; followers/following lists; follow alerts (new post / new artwork / new event) via in-app + push; Staff Picks block (admin-curated ≤12 artworks + ≤6 events) on Home and Feed; trending + recommended events rails.

### 4.4 Messaging (real-time)
Threads between any two users; 7 attachment kinds (artwork, studio, image, commission, auction, offer, order) enriched inline; read receipts (delivered/read, single/double check); typing indicator (6s TTL); 6 emoji reactions (heart, fire, mind_blown, wow, clap, eye — one per user per message, toggle/replace); full-text search; throttled push (one per sender per hour). Transport: WebSocket `wss://…/api/ws?token=JWT&rooms=…` with rooms `user:{id}` and `auction:{id}`, reconnect/backoff, polling fallback.

### 4.5 Notifications
In-app feed with ~60 kinds (label + icon + color + click-through route), unread badge, mark read/delete. **Web Push (VAPID)** with per-category preferences: dm, bid, offer, follow, commission, mention, post, event, social, system — all default on. Push helper checks prefs before fan-out and prunes dead endpoints.

### 4.6 Commerce
- **Cart + Stripe Checkout** for buy-now (multi-seller carts create one order with `artist_payouts[]` per seller).
- **Make an Offer:** 50–100% of list; seller accept/decline/counter (> original, ≤ list); buyer accept-counter/decline/withdraw; paying an accepted offer auto-expires competing offers.
- **Live Auctions:** scheduled `start_at` auto-activate, atomic compare-and-swap bidding (409 to loser), eBay-style proxy bidding (ceiling jumps in one atomic write), watchers notified on leader change and <1h ending, 48-hour payment window with next-bidder forfeit chain, real-time bid updates via WebSocket + LIVE indicator.
- **Commissions:** request → artist accept/decline/counter (quote with amount, sketch image, note, timeline) → deposit (Stripe) → progress updates → delivered → buyer approves → balance charged. Kinds: `art` and `flip` (furniture: type, dimensions, condition, handoff dropoff/pickup/ship, city). 7-stage escrow timeline UI.
- **Fees (settings.global):** `commission_percent` 4.0 (default; Founding Artists lock 4% for life; standard rate may rise later), `processing_percent` 2.9 + `processing_fixed` 0.30 **paid by seller**, `upload_fee`. Fee preview endpoint and calculator in Studio → Payouts. $100 sale → platform $4.00, Stripe $3.20, artist $92.80.
- **Founding Artists:** first 500 artists (cap configurable) get `founding_member`, `founding_number`, `locked_commission_percent`; badges shown on cards/profiles. **0% fee waiver** window for new artists: 30 days or 5 sales (configurable), with 7-day/1-day reminder emails; admin can grant/extend.
- **Art Core Pro:** Stripe Billing subscription, $12/mo or $99/yr (lookup keys `pro_monthly`/`pro_yearly`), founders get coupon `founding50` (50% forever). Perks: Pro themes, boosted marketplace placement (sort Pro first), faster payouts (5-business-day hold, same-day on delivery), Pro badge, custom theme. Webhook syncs `customer.subscription.*`; portal/cancel/resume endpoints.

### 4.7 Payments & payouts (Stripe Connect — Separate Charges & Transfers)
- Buyer pays the platform. **Funds are held on the platform; nothing goes to the artist at checkout.**
- Artist onboards to **Stripe Connect Express** from Studio → Payouts (onboarding link, status, Express dashboard link).
- Each `order.artist_payouts[]` entry: `{artist_id, artwork_id, gross, net, status: held|transferred|pending|released|reversed, release_at, hold_reason, stripe_transfer_id}`.
- **Release rules:** buyer confirms receipt → `release_at = now + 2 days` (Pro: now). No confirmation → 10 business days after sale (Pro: 5). Dispute/not-received → **frozen** (`release_at = null`) until admin resolves; reject → unfreeze with 2-day countdown. A sweep every 10 min transfers due payouts via `stripe.Transfer`; artists without Connect fall to `pending` (manual settlement).
- **Refunds (admin):** full/partial on orders and commissions; reverses transfer + application fee when a transfer exists; sold artworks relist on full refund; `clawback_needed` flag for already-released funds; notifies all parties.
- **Admin Stripe tab:** platform account status, claim link, save live keys (validated against Stripe, stored in settings), test/live switch; keys applied at startup and on save.

### 4.8 Fulfillment & anti-chargeback (Depop-style)
Pipeline: `pending → shipped → carrier_delivered → delivered | not_received`.
1. **Seller cannot mark shipped without carrier + tracking number** (422).
2. Shipping creates an **EasyPost Tracker** when `EASYPOST_API_KEY` is set (carrier normalized: USPS/UPS/FedEx/DHLExpress/…); signed `tracker.updated` webhook (HMAC, deduped by event id) + 30-min polling flip the order to `carrier_delivered`. Without a key: seller taps **"Tracking shows delivered"**, or the sweep estimates delivery **7 days** after ship.
3. On `carrier_delivered`, buyer gets in-app + push + email, and a **full-screen, un-dismissable modal appears on every page** (Escape/backdrop blocked, body scroll locked, polls on route change/60s/focus) with two buttons: **"I received my item"** → `delivered`, payout countdown starts, review unlocked; **"I did not receive it"** (2-step confirm) → `not_received`, payout frozen, **dispute auto-opened** (reason `not_received`, tracking proof attached), seller + admins notified.
4. **No answer in 3 days → auto-confirmed** (`confirmed_how: auto`).
5. Order detail shows fulfillment chip, tracking timeline (live: status chip, events, ETA, carrier link), seller/buyer action buttons; selling queue shows "Delivered — awaiting buyer confirmation".
6. Disputes (buyer): reasons damaged / not_received / not_as_described / other, description ≥10 chars, ≤6 photos; one open per order; admin resolves refund_full / refund_partial / reject with note. Any open dispute freezes payouts.
7. Reviews (1–5 + text) gated behind `delivered`. **Certificate of Authenticity** PDF per purchased artwork (dark-branded, QR to artwork, cert no. `AC-XXXXXXXX-XXXXXX`).

### 4.9 Events & ticketing (local art discovery)
- 13 categories (exhibition, gallery_opening, festival, street_art, pop_up, art_class, workshop, auction, meetup, live_painting, museum, market, virtual). Fields: title, description, category, venue, organizer, location {lat,lng,address,city} (Nominatim geocoding), start/end, capacity, free or `ticket_price`, website, ticket_info, images ≤8, tags, `reminders_enabled`, recurrence (weekly/biweekly/monthly × 2–26 → series with `series_id`, edit/cancel "this" or "series").
- Discovery: search, category chips, date presets, free-only, saved-only, sort soonest/trending/distance, **Near me** (geolocation + radius slider 5–500 km, map with category-colored pins, radius circle), list grouped by day, map view (Leaflet). Trending score = `(rsvps_48h×3 + total)×soon_boost`. Recommendations (+3 followed host, +2 category affinity, +1 same city, +1 trending).
- RSVP (free) or **Get Ticket** (Stripe; host payout via Connect); capacity → **waitlist** with position emails and **15-minute auto-charge holds** when a seat frees; **gift tickets** by email (public token page, QR emailed, auto-claimed on signup); QR ticket (`artcore:ticket:{rsvp_id}:{event_id}`), host **camera scanner** check-in (html5-qrcode) or paste; Tickets wallet page with Upcoming/Past, presentation-mode QR, **PNG wallet pass** (Web Share / download; native Apple/Google passes pending credentials); **calendar subscription** (.ics feed per user, Google/Apple links); 24h + 1h reminders (+ gift recipients); host tools: edit, cancel (auto-refunds), broadcast to attendees (DM + email + push), analytics modal (RSVPs, paid/free, check-in rate, fill rate, revenue gross/fee/net, RSVP curve) with CSV export (formula-injection safe); host pages; share OG cards; save events; report.

### 4.10 Search, rankings, growth
Global search across artists + artworks (+ events). Rankings leaderboard (bronze → legendary tiers). Share endpoints `/api/share/{artwork|studio|event}/{id}` return crawler-friendly OG HTML + instant redirect; PNG OG cards rendered server-side (1200×630). Newsletter signup.

### 4.11 Moderation & safety
Report button on artworks, posts, users, events, hosts (reason + details, one open per target). Admin Reports tab: dismiss / warn_user / remove_content / suspend_user, resolves all reports on a target together. Rate limits: login 10 fails/email + 30/IP per 15 min (429 + Retry-After), demo-login 30/IP, OTP resend 3/10 min, 2FA lockout after 8 wrong codes decaying in 15 min. All transactional emails HTML-escape user input. Prohibited-items / package-contents liability disclaimer in Terms; register requires 18+ & Terms consent.

### 4.12 Admin Command Desk (`/admin`)
Tabs: Settings (commission, processing fee, upload fee, currency, waiver days/sales, founding enabled/rate/cap, **demo sign-in buttons toggle**), Stripe (setup card + keys), Featured/AOTW curation, Staff Picks, Orders, Refunds, Disputes, Reports, Mentorship inbox, Waivers (grant/extend, founding backfill).

### 4.13 Internationalization
react-i18next; language picker in navbar saved to `localStorage` + `users.language`. 9 locales: en, es, fr, de, pt, it, ja, ko, zh. Covered: nav/footer, Home, Auth, Onboarding, Explore/Marketplace filters, Artwork/Event CTAs, Cart, Notifications labels, Studio/Orders/Messages blocks; remainder English with fallback.

### 4.14 Emails (Resend) — dark, lime-accent, table-based HTML
Ticket receipt · refund notice · waitlist position · waitlist seat open (with 15-min hold link) · event broadcast · gift ticket (QR) · gift sent receipt · gift reminder · OTP code · waiver ending (7d/1d) · **"Did your order arrive?"** delivery confirmation. Sender `refunds@artcorestudio.net` with sandbox fallback until DNS verified.

---

## 5. Data model (MongoDB collections — key fields)

- `users` {id, email, password_hash, name, role, bio, avatar, cover_image, approved, language, stripe_connect_status, stripe_account_id, founding_member, founding_number, locked_commission_percent, waiver_until, waiver_sales_left, pro {status, price_id, current_period_end, customer_id}, twofa_enabled, twofa_method, twofa_secret, recovery_codes[], trusted_devices[], twofa_fail_count, twofa_fail_at, is_demo, onboarded, created_at}
- `artworks` {id, artist_id, title, description, medium, dimensions, year, edition, price, images[], status, section, furniture_type, materials, before_image, delivery[], location, views, likes_count, created_at}
- `studios` {artist_id, live: config, draft: config, published_at} — config = {theme, accent, lighting, texture, texture_intensity, sections[], featured_ids[], story{}, commissions_open, commission_blurb}
- `posts`, `post_likes`, `post_comments`, `likes`, `comments` (parent_id), `follows`, `saves`, `collections`, `artwork_views`, `studio_visits`
- `messages` {id, thread_id, from_id, to_id, text, attachment{kind,…}, delivered_at, read_at, reactions[]}, `typing`
- `notifications` {id, user_id, kind, read, created_at, …context ids}, `notification_prefs`, `push_subscriptions`, `push_config`
- `orders` {id, buyer_id, items[{artwork_id, artist_id, price, quantity}], total, processing_fee, status, refunded, refund_amount, dispute_status, dispute_id, fulfillment {status, carrier, tracking, note, shipped_at, tracker_id, tracking_status, tracking_events[], est_delivery, tracking_url, tracking_source, carrier_delivered_at, carrier_delivered_source, confirm_deadline, delivered_at, confirmed_how, not_received_at}, artist_payouts[], created_at}
- `payment_transactions` {id, session_id, payment_intent, kind: buyer_order|auction_win|offer_payment|commission_payment|event_ticket|event_ticket_gift|upload_fee|pro, amount, status, user_id, refunded, …}
- `offers`, `auctions` {…, current_bid, current_bidder_id, proxies[], start_at, end_at, status, payment_deadline}, `bids`, `auction_watchers`
- `commissions` {kind, furniture{}, quote{}, deposit, balance, status, progress[]}
- `disputes` {id, order_id, buyer_id, seller_id, reason, description, images[], tracking_proof{}, auto_opened, status, resolution, refund_amount, admin_note, history[]}
- `reviews`, `reports`
- `events` {…, series_id, series_seq, series_total, reminders_enabled, cancelled, reminder_24h_sent, reminder_1h_sent}, `event_rsvps` {event_id, user_id|null, paid, amount, session_id, payment_intent, refunded, checked_in, gift, gift_token, gift_email}, `event_saves`, `event_waitlist`, `waitlist_holds`, `event_broadcasts`, `calendar_tokens`
- `settings` {id:"global", commission_percent, upload_fee, currency, processing_percent, processing_fixed, waiver_enabled, waiver_days, waiver_max_sales, founding_enabled, founding_rate, founding_cap, demo_login_enabled, staff_picks{}, aotw_artwork_id, stripe_live_keys…}
- `files` (object-storage registry), `rate_limits` (TTL), `webhook_events` (dedupe), `newsletter`

All ids are UUID strings (never expose Mongo `_id`). Timestamps ISO-8601 UTC.

---

## 6. API surface (all under `/api`, JWT bearer unless public)

Auth `/auth/{register,login,demo-login,me,2fa/*}` · Artworks `/artworks` CRUD + `/upcycle/meta` + `/files/{path}?w=` · Social `/feed/home`, `/artworks/{id}/{like,comments,share,save}`, `/collections`, `/users/{id}/{follow,followers,following,badges}` · Posts `/posts` · Studio `/studio/{artist_id}`, `PATCH /studio`, `/studio/publish`, `/studio/templates`, `/studio/apply-template`, `/studio/ai-design`, `/studio/analytics/me` · Messages `/messages/threads`, `/messages/thread/{user_id}` (+ `/typing`, `/read`), `/messages/{id}/react`, `/messages/search` · Notifications `/notifications`, `/notifications/prefs`, `/push/*` · Commerce `/payments/checkout`, `/payments/status/{session}`, `/payments/webhook`, `/offers/*`, `/auctions/*`, `/commissions/*`, `/orders/{mine,selling}`, `/orders/{id}`, `/orders/{id}/{ship,carrier-delivered,confirm-received,not-received,mark-delivered,dispute,certificate/{artwork_id},tracking}`, `/orders/confirmations/pending`, `/reviews`, `/tracking/config`, `/tracking/easypost/webhook` · Connect `/connect/{onboarding-link,status,dashboard-link}` · Pro `/pro/{plans,status,checkout,cancel,resume,portal}` · Events `/events` (+ filters), `/events/{id}/{rsvp,save,waitlist,attendees,my-ticket,my-ticket/pass.png,check-in,analytics,analytics.csv,broadcast,broadcasts}`, `/events/mine/{tickets,saved}`, `/events/lists/trending`, `/events/recommended`, `/events/hosts/{id}`, `/events/gift/{token}`, `/payments/events/{id}/{ticket,gift}`, `/calendar/token`, `/calendar/{token}.ics` · Growth `/share/*`, `/staff-picks`, `/newsletter` · Search `/search?q=` · Rankings `/rankings` · Reports `/reports` · Admin `/admin/{settings,stripe,refunds,disputes,reports,staff-picks,waiver,...}` · Realtime `WS /ws` · Public `/settings`, `/settings/fee-preview?gross=`.

---

## 7. Background jobs (single loop every 10 min at startup)

event reminders (24h/1h, gift recipients) · waitlist hold expiry + promotion · payout release sweep · EasyPost tracker polling (30-min stale) · delivery sweep (7-day estimate → carrier_delivered; 3-day deadline → auto-confirm) · waiver reminders · auction scheduled start / ending-soon / payment deadline checks · demo-date roll-forward.

---

## 8. Integrations & env

`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (re-synced at boot = rotation), `DEMO_ARTIST_PASSWORD`, `DEMO_COLLECTOR_PASSWORD`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_MODE`, `STRIPE_ONBOARDING_URL`, `RESEND_API_KEY`, `SENDER_EMAIL`, `SENDER_FALLBACK`, `EASYPOST_API_KEY`, `EASYPOST_WEBHOOK_SECRET`, `PUBLIC_APP_URL`, LLM key for Studio AI, object-storage credentials. Frontend: `REACT_APP_BACKEND_URL` only.

Frontend libs: react-router v6, axios, tailwind, shadcn/ui, lucide-react, sonner, framer-motion, react-i18next, leaflet + react-leaflet, html5-qrcode. Backend libs: fastapi, motor, pydantic v2, stripe, resend, easypost, pyotp, PyJWT, bcrypt, qrcode, Pillow, reportlab, pywebpush.

---

## 9. Seed / demo world

Seed admin from env. Two demo accounts (`demo.artist@…`, `demo.collector@…`) with **one-tap "Enter as Artist / Collector" buttons on /login** (server-side `/auth/demo-login`, admin-toggleable, off for public launch). Optional demo world: 8 fictional artists, 3 collectors, 27 artworks incl. 5 upcycle before/after, 16 posts, 8 auctions, 5 offers, 5 commissions, 4 orders, 10 events (paid, sold-out w/ waitlist, weekly series, past checked-in), DMs, follows, notifications — all tagged `seed: "demo_v1"` and idempotent.

---

## 10. Quality bar & testing

Every interactive element and every critical piece of info has a unique kebab-case `data-testid`. Never return raw Mongo documents. Validate at boundaries (Pydantic). Idempotent webhooks. Atomic writes for money/bids. Backend pytest suites per feature + Playwright E2E at 1920×800 and 390×844. Zero horizontal overflow on mobile.

---

## 11. Launch checklist (business side)

Stripe live keys + claimed platform account · Resend domain DNS verified · deploy to `artcorestudio.net` with `REACT_APP_BACKEND_URL`/`CORS_ORIGINS`/`PUBLIC_APP_URL` updated · real founder content replacing demo world · demo buttons off · attorney review of `/legal/*` · optional: EasyPost key for live tracking, Apple/Google Wallet credentials for native passes.
