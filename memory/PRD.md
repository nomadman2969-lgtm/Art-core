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



## Realtime Messaging Polish + PWA + Push (Feb 26, 2026)

### Direct Messaging v3
- **Typing indicators**: `POST /api/messages/thread/{user_id}/typing` upserts a `typing` doc with 6s TTL. `GET /messages/thread/{user_id}` returns `other_typing: bool`. Frontend throttles the signal to every 2.5s.
- **Message reactions**: `POST /api/messages/{message_id}/react` with `{emoji}` in allowlist (heart, fire, mind_blown, wow, clap, eye). Same emoji toggles off; different emoji replaces (one active reaction per user per message). 403 for non-thread members, 400 for invalid emoji.
- **Frontend UI**: Hover a bubble → smile-icon reveals (always-40%-visible on mobile). Tap → floating picker with all 6 emojis. Applied reactions render as colored chips under the bubble (chip lit green if it's yours). Typing bubble shows the other user's first name + 3 bouncing lime dots.

### PWA (installable app)
- `manifest.json` with name, icons (192/512 maskable), theme #0A0A0C, standalone display, 3 shortcuts (Feed, DMs, Studio).
- `service-worker.js`: navigation network-first with offline shell fallback; stale-while-revalidate for static assets; skips `/api/`.
- 3 icons generated (192, 512, apple-touch-180) with lime badge + "A".
- `index.html` updated with manifest link, apple-touch-icon, PWA meta tags, and app title.
- SW auto-registers in `index.js` (https only).

### Feed Composer (`/feed`)
- New `FeedComposer.js` modal — 9 kind chips, textarea with @mention support + live counter, image OR video upload (mutually exclusive), Post button.
- Three entry points on `/feed`: top-right green "New Post" button, quick-post prompt card (avatar + placeholder), mobile floating action button.
- Only visible for `role in ("artist", "admin")`.

### Push Notifications (Web Push / VAPID)
- New `push.py` module with:
  - Auto-generated VAPID keypair on first run, persisted in `push_config` MongoDB collection.
  - `GET /api/push/vapid-public-key` — returns url-safe b64 for `applicationServerKey`.
  - `POST /api/push/subscribe` / `POST /api/push/unsubscribe` — idempotent per (user, endpoint).
  - `GET /api/push/subscriptions/mine`, `POST /api/push/test` — utilities.
  - `send_push(user_id, title, body, url)` helper — fans out to all subscriptions, prunes dead endpoints (404/410).
- **Triggers wired** in: `messages.py` (new DM), `auctions.py` (outbid × 2 paths + auction ending soon), `offers.py` (offer received + accept/decline/counter).
- Frontend: `usePushSubscription()` hook + toggle card at top of `/notifications` with Enable / Send Test / Turn Off. Service worker's `push` + `notificationclick` handlers focus the correct URL.

### Testing status
- Backend: All new endpoints curl-tested (typing, react toggle/replace/invalid, subscribe/unsubscribe/vapid).
- Frontend: Smoke screenshots of Feed Composer modal, Messages reactions/typing UI, Notifications push card — all rendering correctly.
- testing_agent iteration 12 dispatched but not returned before this write; iteration_13 will re-run with push included.


## Notification Prefs + Events/Map + Studio Refactor (Feb 27, 2026)

### Notification Preferences
- `notification_prefs` collection with 7 category flags: dm, bid, offer, follow, commission, mention, post (all default true).
- Endpoints: `GET /api/notifications/prefs` and `PATCH /api/notifications/prefs`.
- `KIND_TO_CATEGORY` map + `push_allowed(user_id, kind)` helper.
- `send_push()` now accepts a `kind` parameter and checks prefs before sending; all 5 push call-sites updated (new_message, outbid ×2, auction_ending, offer_received, offer_action).
- Frontend: `/notifications` has a "Preferences" toggle button revealing a card of 7 stylized on/off toggles, each colored per category.

### Events & Map (Live!)
- Backend `events.py` module: `POST /api/events` (artist-only host), `GET /api/events` (with `category`, `host_id`, `upcoming_only`, `near_lat/near_lng/radius_km` haversine filter), `GET/DELETE /api/events/{id}`, `POST /api/events/{id}/rsvp` (toggle), `GET /api/events/{id}/attendees`.
- 8 categories: gallery_opening, pop_up, festival, meetup, workshop, live_painting, virtual, market.
- Location model with lat/lng/address/city; free vs paid events with ticket_price.
- RSVP fires host notification (once per user).
- Cancel event → notifies all RSVPed users.
- Frontend: `leaflet` + `react-leaflet` installed. `/events` page with Map view (auto-fitBounds, click pins for popup) + List/Grid view, category filter chips, Host CTA (artist/admin only). `/events/:id` detail with map preview, RSVP toggle button, attendee list, host actions (cancel).
- Create Event modal has OpenStreetMap Nominatim geocoding — enter address+city, click "Find coordinates" to auto-fill lat/lng.
- Nav badge "Soon" removed from Events.

### Studio Refactor
- `pages/StudioEditor.js` shrunk from **1205 → 314 lines** (74% reduction).
- Extracted 11 subcomponents to `components/studio/StudioParts.js`:
  SectionH, Stat, BackgroundEditor, PolishButton, TemplatesPicker, SectionsEditor, ImageBlockEditor, FeaturedEditor, StoryEditor, PostsEditor, PayoutsPanel, ArtworkRow, CommissionRequestsPanel.
- Also exports `SECTION_KINDS` and `LAYOUT_OPTIONS` constants.
- All `data-testid`s preserved verbatim; no functional changes.

### Testing
- Backend: prefs GET/PATCH curl-verified, events create/list/RSVP/toggle curl-verified.
- Frontend: smoke-tested — Events map renders 3 pins auto-fit-bounded, side list, filter chips; Notification prefs card toggles render; Studio Editor tabs still load after refactor.



## Event Push Alerts + Nearby + Ticket Payments (Feb 28, 2026)

### Event Push Alerts
- `send_push()` called in `events.py` on RSVP (host gets alert with attendee name + event) and cancellation (each attendee gets alert).
- New `event` category added to `notification_prefs` (default true).
- New notification kinds mapped: `event_rsvp`, `event_cancelled`, `event_reminder`, `event_ticket_paid`.
- `Notifications.js` KIND_META extended with event kinds + colored icons.
- Route resolver: notifications with `event_id` link directly to `/events/:id`.

### Nearby Events (Geolocation)
- Frontend `/events`: **Near me** button uses `navigator.geolocation` (5min cache); once granted, shows a lime-dashed radius circle on the map + a "you are here" lime pulsing dot marker.
- Radius slider (5–500km, default 50).
- Map auto-fits to include both user location and any events in range.
- Backend haversine filter already supported the `near_lat`, `near_lng`, `radius_km` params — now used from the UI.
- Empty state adapts: "No events in range" when filtering vs "No events yet" globally.
- Counter shows `X events within Ykm` or `X events worldwide`.

### Event Tickets (Real Stripe)
- New `POST /api/payments/events/{event_id}/ticket` endpoint:
  - Rejects free events (400), sold-out events (capacity check), duplicate purchases.
  - Uses `build_transfer_options()` for Stripe Connect destination charges — host with `payouts_enabled` gets funds routed directly (minus platform commission).
  - Cancel URL routes back to the event page.
  - Creates `payment_transactions` row with `kind: "event_ticket"`, `event_id`, `host_id`, `amount`.
- `_apply_paid()` handles `event_ticket` — creates the RSVP row (idempotent), fires host push + buyer confirmation notification, marks RSVP as `paid: true` with amount + session_id for future refunds.
- Frontend event detail:
  - Paid event RSVP button becomes **"Get Ticket · $X"** (lime CTA) that redirects to Stripe.
  - Free events still use the simple RSVP toggle.
  - Payment success page (`Cart.js`) has an `event_ticket` variant → "You're going" headline + "See Events" CTA.

### Testing
- Backend curl: paid ticket returns valid Stripe URL; free-event ticket returns 400; near-me radius filter narrows results correctly; prefs default includes `event: true`.
- Frontend screenshots: near-me active with radius slider + lime location dot + circle + narrowed list; paid event detail shows "Get Ticket · $25" button + mini-map + cancel action.



## Reminders + Refunds + QR + Feed Rail (Mar 1, 2026)

### Event Reminder Push
- `check_event_reminders()` in `events.py` — fires 24h and 1h before `start_at`, idempotent via `reminder_24h_sent` / `reminder_1h_sent` markers.
- Opportunistically invoked from `GET /api/events` (cheap, no cron needed).
- Fans push + in-app notification (kind=`event_reminder`) to every RSVP'd user.

### Ticket Refunds
- On event cancel (`DELETE /api/events/{id}`) — iterates every paid `payment_transactions` row (kind=event_ticket, not yet refunded), calls `stripe.Refund.create(payment_intent=..., reverse_transfer=True, refund_application_fee=True)`, updates tx + RSVP with `refunded: true`, notifies attendees with amount.
- `_apply_paid()` now persists `payment_intent` on `event_ticket` transactions so refunds are direct (no session retrieval needed).
- Cancel response returns `{cancelled, refunded, failed, amount}` summary.

### Attendee QR Codes
- `qrcode` lib installed. New endpoints:
  - `GET /api/events/{id}/my-ticket` — returns `{rsvp_id, qr_payload, qr_image (data URL PNG), event_title, checked_in, ...}`. Rejects if no RSVP / cancelled / refunded.
  - `POST /api/events/{id}/check-in` — host/admin scans a payload; validates format (`artcore:ticket:{rsvp_id}:{event_id}`), matches event, marks `checked_in: true` (idempotent, returns `already: true` on rescan).
- Frontend `EventDetail.js`:
  - **Your Ticket** panel (when user has RSVP + event not cancelled): show/hide button, QR image on white background, attendee name, price, short ID.
  - **Door Check-in** panel (host only): paste-payload input + submit → toast confirms check-in with attendee name; second scan flags "Already in".

### Events on Feed
- `HomeFeed.js` fetches upcoming events near the user (geolocation optional, 100km radius, falls back to global).
- Horizontal scrollable **Upcoming Events** rail between the composer prompt and filter chips — 8 cards max, cover image or gradient by category, category chip, price badge for paid events, date + city.
- **See all →** link to `/events`.

### Testing
- Backend curl: RSVP → QR generation → check-in → duplicate scan (already) → invalid QR (400) → non-host attempt (403) → cancel (refund summary) → post-cancel my-ticket (400). All pass.
- Frontend screenshots: QR + check-in panel rendering on event detail; upcoming events rail rendering on home feed with mixed free/paid cards.



## QR Scanner + Wallet + Refund Emails + Trending (Mar 2, 2026)

### QR Camera Scanner
- Installed `html5-qrcode`. Host check-in panel on `/events/:id` now has **Scan / Paste** mode toggle.
- Scan mode: uses rear-facing camera via `Html5Qrcode`, decodes 10fps, auto-submits check-in. Debounced to prevent duplicate submits within 1.5s.
- Graceful fallback: camera denied / unavailable auto-switches to Paste mode with toast.
- Last-check-in banner shows checked-in / already / error states with color.

### Ticket Wallet (`/tickets`)
- New backend `GET /api/events/mine/tickets?upcoming_only=<bool>` — every RSVP for the current user with event + payment + check-in state.
- New `/tickets` page + **TICKETS** nav link (top nav, next to Orders).
- Upcoming / Past & Cancelled tabs; ticket cards show cover, category chip, price/refunded/checked-in badges, date, city, and a **Show QR** button.
- QR modal is a white-background presentation-mode ticket (attendee name + short ID) — pull-QR on demand.

### Refund Emails (Resend)
- Installed `resend`. New `/app/backend/emails.py` with `send_email(to, subject, html)` (non-blocking via `asyncio.to_thread`, graceful fallback from `refunds@artcorestudio.net` → sandbox `onboarding@resend.dev` if the custom domain isn't yet DNS-verified).
- Templates: `refund_email_html()` (event cancellation), `ticket_receipt_html()` (successful purchase). Both use table-based inline-CSS HTML styled to match the Art Core dark aesthetic with the lime accent.
- Triggered from `events.cancel_event()` for every paid RSVP + from `payments._apply_paid()` for `event_ticket` kind (buyer receipt).
- All sends fire-and-forget so payment/cancel latency is unaffected.
- `.env` keys: `RESEND_API_KEY`, `SENDER_EMAIL=refunds@artcorestudio.net`, `SENDER_FALLBACK=onboarding@resend.dev`.
- Delivery verified against Resend's `delivered@resend.dev` test inbox → returned message id.

### Event Trending
- New `GET /api/events/lists/trending` — scores upcoming events by:
  `(recent_rsvps_48h × 3 + total_rsvps) × soon_boost` where `soon_boost = 1.0 → 2.0` as event date approaches (7d window). Optional `near_lat`, `near_lng`, `radius_km` filter.
- HomeFeed rail now uses this endpoint (still location-aware).
- Rail card gets a red **🔥 Trending** badge when `recent_rsvps_48h >= 3`.
- Rail title changed to **Trending Events**.

### Testing
- Backend curl: trending endpoint returns ordered list (Neon Rooftop Party ranked 1st with score 4.0 vs 0.0 for others); my/tickets returns admin's RSVP; Resend send returned `True` via test inbox.
- Frontend screenshots: Tickets wallet with upcoming card, white QR modal, home feed with Trending header + top-scoring event ranked first.

### Bug fix
- `App.js` referenced undefined `ProtectedRoute` → replaced with the existing `RequireAuth`.



## Recurring + Waitlist + Analytics (Mar 3, 2026)

### Recurring Events
- New `Recurrence` pydantic model: `{frequency: weekly|biweekly|monthly, count: 2-26}`.
- `POST /events` with `recurrence` generates all sibling events in one call, sharing `series_id` and `series_seq/total` fields.
- `DELETE /events/{id}?cancel_series=true` cancels every future sibling at once. Frontend prompts user to cancel whole series if event is part of one.
- Frontend Create modal: **"Make it a recurring series"** checkbox → reveals Frequency select + Count input with live "Creates N events, each X days apart" hint.
- Event detail page shows **"Session N/M in this series"** indicator.

### Waitlist
- `event_waitlist` collection with `{event_id, user_id, user_name, user_email, notified, created_at}`.
- `POST /events/{id}/waitlist` — idempotent toggle; returns `{on_waitlist, position}`.
- `GET /events/{id}/waitlist` — host-only summary.
- `_promote_from_waitlist()` — when a free RSVP is cancelled OR a paid RSVP is refunded, notifies + emails + pushes the first un-notified user.
- Frontend event detail: when event is full, RSVP button auto-swaps to a purple **"Join Waitlist"** button; once on the list, it shows position and lets them leave.
- Email template `_waitlist_invite_html` matches the Art Core aesthetic — sent via Resend when a spot opens.

### Event Analytics (host mini-dashboard)
- `GET /events/{id}/analytics` — host/admin only. Returns:
  - `total_rsvps`, `paid_rsvps`, `free_rsvps`, `refunded_rsvps`, `checked_in`, `check_in_rate` (%)
  - `capacity`, `fill_rate` (%)
  - `waitlist` count
  - `revenue_gross`, `revenue_refunded`, `platform_fee` (uses live settings.commission_pct fallback 10%), `net_to_host`
  - `rsvp_curve` — daily counts since event creation, capped at 60 days
- Frontend: **"View analytics"** button in host sidebar opens a full modal with 4 stat boxes, revenue breakdown card (gross/fee/net), fill-rate progress bar, and a CSS-only bar chart of the RSVP curve.

### Testing
- Backend curl: recurring create → 3 sibling events; capacity full returns 400 "join the waitlist"; waitlist join returns position 1; analytics returns full payload for host, 403 for non-host.
- Frontend screenshots: sold-out event with purple Join Waitlist + series indicator; analytics modal with 3 RSVPs / 100% fill rate; Create Event with recurrence checkbox active + live hint.

## Upcycle Section + 3% Platform Fee + Local Pickup (Mar 10, 2026)
- **Upcycle** (`/upcycle`, nav "Upcycle"): furniture turned into art. Artworks gained `section` (art|upcycle), `furniture_type` (chair/table/dresser/cabinet/lamp/mirror/shelf/bench/other), `materials`, `before_image` (Before/After toggle on cards + detail), `delivery` ['ships','local_pickup'] (eBay-style: seller ships their own way or local pickup), `location {lat,lng,city}`.
- API: `GET /api/upcycle/meta` (type counts); `GET /api/artworks?section=&furniture_type=&pickup_only=&near_lat=&near_lng=&radius_km=` (adds `distance_km`, sorted by distance). Upload form (`/studio/upload?section=upcycle`) has section toggle + upcycle-only fields (type, materials, delivery toggles, city geocode via Nominatim, before photo).
- 5 demo upcycle pieces seeded with generated before/after images (`/app/backend/seed_demo.py` image cache + `/tmp/seed_upcycle.py` logic — re-create under /app if needed).
- **Platform fee is now 3%** (`settings.global.commission_percent = 3.0`, defaults in payments/admin/server; event analytics reads the same key). Money flow: Stripe Connect destination charges → artist 97% to their connected account, 3% application fee + $5 listing fee stay in the platform Stripe balance.
- Testing — iteration_18: 18/18 backend + frontend pass (desktop + mobile).

### Queued (user-picked, not yet built)
- Artist Analytics dashboard (studio visits, saves, follower growth, top pieces)
- Gift Tickets (buy a ticket for a friend by email, QR delivered)
- Two-Factor Login (TOTP authenticator; integration_expert auth playbook already fetched — bcrypt/PyJWT; use pyotp)

## Follow Alerts + Staff Picks + Calendar Sync + Mobile Feed (Mar 10, 2026)
- **Follow alerts** (`backend/engage.py notify_followers`): followers get in-app + push (`followed_new_post` on studio post create, `followed_new_event` on event/series create, `followed_new_artwork` when an artwork goes live after the upload fee). Labels in Notifications.js; category "social".
- **Staff Picks**: `GET /api/staff-picks` (public, enriched, drops removed/past items) and `PUT /api/admin/staff-picks {title, blurb, artwork_ids≤12, event_ids≤6}` stored in `settings.global.staff_picks`. `components/home/StaffPicks.js` on Home (full) + Feed (compact); Admin **Staff Picks** tab (`components/admin/StaffPicksPanel.js`) with numbered tile picker.
- **Calendar sync**: `POST /api/calendar/token` (per-user secret, URL derived from request host), `DELETE` to rotate, `GET /api/calendar/{token}.ics` — RSVP'd "(Going)" + saved "(Saved)" events, 24h VALARM, GEO, 6h refresh hint. `components/CalendarSubscribe.js` on /tickets with Google / Apple(webcal) / copy / regenerate.
- **Mobile feed**: `/feed` root gets `overflow-x-hidden`; rails scroll internally (verified scrollWidth == 390). Shared `copyText()` helper in api.js with execCommand fallback.
- Testing — iteration_17: 8/8 backend + frontend pass (one LOW clipboard hardening applied afterwards).

## Moderation + Recommendations + Host Pages + Thumbnails (Mar 10, 2026)

### Report Content — `backend/reports.py`
- `POST /api/reports {target_type: artwork|post|user|event, target_id, reason, details}` (auth; no self-reports; one open report per user/target). Admins notified (`report_opened`).
- Admin: `GET /api/admin/reports[?status]`, `GET /api/admin/reports/stats`, `POST /api/admin/reports/{id}/resolve {action: dismiss|warn_user|remove_content|suspend_user, note}` — resolves all open reports on that target together; remove_content → artwork status `removed` / post `hidden` / event cancelled / user `approved=False`; notifications `report_resolved` (reporters) + `moderation_action` (owner). Feed + studio post queries filter `hidden != True`.
- Frontend `components/ReportButton.js` (artwork detail, studio header, feed post cards, event detail, host page) + Admin **Reports** tab (`components/admin/ReportsPanel.js`, grouped by target with report counts).

### Event Recommendations — `GET /api/events/recommended`
- Scores upcoming events: +3 followed host, +2 category matches saved/attended events, +1 same city, +1 trending (≥5 RSVPs); excludes RSVP'd/saved/own, one per series. Returns `reason` text. Rail `components/events/RecommendedEvents.js` on /events and /feed ("Picked for you").

### Host Pages — `GET /api/events/hosts/{user_id}`, route `/host/:id` (`pages/HostPage.js`)
- Cover/avatar header, stats (events hosted, upcoming, total attendees, followers), category chips, Follow (reuses /users/{id}/follow), Studio link, share, report; Upcoming/Past tabs with EventCards. Event detail "Hosted by" and card organizer lines link here.

### Faster image loading
- `GET /api/files/{path}?w=240|480|960` → resized progressive JPEG (Pillow), cached in object storage under `thumbs/{w}/{path}`, headers `Cache-Control: public, max-age=31536000, immutable`, `CDN-Cache-Control`, `ETag`. NOTE: the preview ingress overrides Cache-Control to no-store; production edge should honor it. `api.js thumbUrl(path, w)`; grids/feeds (ArtCard, HomeFeed, Artists, HomeExtras, Events, admin panels) use thumbnails; detail pages stay full-res. Typical saving 258 KB → 36 KB.

### Demo evergreen
- `seed_demo.refresh_demo_dates()` runs at backend startup: rolls seeded upcoming events forward by whole weeks once they pass (series shift together and are re-spaced weekly).

### Testing — iteration_16: backend 18/19 (1 = ingress Cache-Control, infra) + frontend 100%.

## Local Art Discovery (Events rebuild) + Onboarding + Share Cards + Badges (Mar 8, 2026)

### Events → local art discovery system
- **13 categories** (`CATEGORY_META` in `events.py`, served by `GET /api/events/meta/categories`): exhibition, gallery_opening, festival, street_art, pop_up, art_class, workshop, auction, meetup, live_painting, museum, market, virtual.
- **Richer event model**: `venue, organizer (defaults to host), website, ticket_info, ticket_url, images[] (gallery ≤8), tags[]` on create + edit; URLs auto-prefixed https://.
- **Discovery API** `GET /api/events` params: `q` (title/description/venue/organizer/city/address/tags regex), `category`, `date_from/date_to` (clamped to upcoming), `free_only`, `sort=soonest|trending|distance`, `near_lat/near_lng/radius_km` (adds `distance_km`), `saved_only` (auth). `_enrich` adds `saved`, `saved_count`.
- **Save events**: `POST /api/events/{id}/save` toggle (`event_saves`), `GET /api/events/mine/saved`.
- **Share**: `GET /api/share/event/{id}` (OG HTML + JS redirect) and `/api/share/og/event/{id}.png` (Pillow-rendered 1200×630 card, red accent).
- **Frontend** `pages/Events.js` rewritten: hero "What's on near you", search bar, Near-me + radius slider, date presets (Today / This weekend / Next 7 days / This month) + custom range, category chips from API, Saved / Free chips, sort select, list grouped by day with rich cards (category + Hot badge, price, venue, organizer, attendee count, save/share/RSVP) and map view with category-colored pins. `components/events/CreateEventModal.js` extracted + new fields. `EventDetail.js`: Save / Share / Add-to-calendar (.ics with 24h alarm) buttons, venue/organizer/website cards, tags, gallery, ticket info + external ticket link.
- No external events API is used — all events are community-hosted on the platform; seeded events are clearly demo-world data (`seed:'demo_v1'`). Geocoding uses OpenStreetMap Nominatim (no key).

### Artist Onboarding — `pages/Onboarding.js` (`/onboarding`, artist/admin only)
- 3 steps: pick theme (PATCH /studio) → upload first piece (POST /artworks; skippable) → publish (POST /studio/publish + `POST /api/onboarding/complete`; upload-fee checkout if configured). Artist signup now redirects here. `public_user` exposes `onboarded`.

### Share cards — `backend/growth.py`
- `/api/share/artwork/{id}`, `/api/share/studio/{id}`, `/api/share/event/{id}` return crawler-friendly OG/Twitter HTML with instant redirect; PNG cards at `/api/share/og/{kind}/{id}.png`. ArtworkDetail + ArtistStudio share buttons now share these URLs.

### Achievement badges — `GET /api/users/{id}/badges`
- Computed live: first_sale, ten_sales, auction_closer, commissioned, event_host, sold_out_show, rising (10 followers), hundred_club, five_star. `components/BadgeRow.js` renders earned chips on the studio header.

### Testing — iteration_15: 17/17 backend + 100% frontend (desktop + mobile).



### Realtime (WebSockets) — `backend/realtime.py`, `frontend/src/hooks/useLive.js`
- `wss://<host>/api/ws?token=<jwt>&rooms=auction:<id>` — in-process hub; rooms `user:{id}` (implicit from JWT) and `auction:{id}`. Verified working through the K8s ingress.
- Publishers: `auctions.py` (both bid paths → `{type:'bid'}`), `messages.deliver_dm` (→ `{type:'dm'}` to both parties), `signal_typing` (→ `{type:'typing'}`).
- Frontend `useLive(rooms, onEvent)` with reconnect/backoff + 25s ping. AuctionDetail shows a lime **LIVE** indicator and refreshes on bid events (polling slows to 20s when connected); MessageThread refreshes on dm/typing (polling 15s). Polling remains the fallback if WS is unavailable.

### Certificate of Authenticity — `backend/certificates.py`
- `GET /api/orders/{oid}/certificate/{artwork_id}` (buyer/seller/admin; 400 if refunded) → dark-branded reportlab PDF: artwork image, title, artist, medium, dimensions, year, edition, buyer, sale date, cert no. `AC-XXXXXXXX-XXXXXX`, QR → `/artwork/{id}?cert=…`, signature block.
- Frontend: **Certificate** button per receipt item (`coa-btn-{i}`) in `components/orders/OrderExtras.js`.

### Order Disputes — `backend/disputes.py`
- Buyer: `POST /api/orders/{oid}/dispute` `{reason: damaged|not_received|not_as_described|other, description ≥10, images[] (storage paths only)}` → `disputes` doc (open). One open dispute per order; new one allowed after resolution. `GET /api/orders/{oid}/dispute`, `GET /api/disputes/mine`.
- Admin: `GET /api/admin/disputes[?status=]`, `POST /api/admin/disputes/{id}/resolve` `{action: refund_full|refund_partial|reject, amount?, note?}` — refunds reuse `admin.refund_order` (Stripe reverse_transfer). Notifications `dispute_opened` (seller + all admins) / `dispute_resolved` (buyer + seller).
- Frontend: **Report a problem** panel on OrderDetail (`dispute-panel`, `open-dispute-btn`, form + photo upload, status chip); Admin **Disputes** tab (`components/admin/DisputesPanel.js`) with note, partial/full refund, reject.

### Mobile-web polish (390px)
- AuctionDetail: no horizontal overflow (`min-w-0` inputs, tighter padding, wrap on watch row). MessageThread: fixed-height card `h-[calc(100dvh-140px)]`, list scrolls internally instead of page-scrolling the composer under the nav. Feed/EventDetail/Tickets verified clean.
- Fixed pre-existing runtime crash: `useEffect(load, …)` returning a Promise in Auctions (ProxyBidPanel, WatchToggle) and Commissions.

### Testing — iteration_14: 9/9 backend + 100% frontend (desktop + 5 mobile screens). `/app/backend/tests/test_iter14_ws_coa_disputes.py`.



### Demo World (`backend/seed_demo.py`)
- Run: `cd /app/backend && python seed_demo.py [--wipe-tests] [--no-images]`. Idempotent — every doc carries `seed: "demo_v1"` and is replaced on re-run. Generated images cached in `demo_assets` (47 images via Gemini `gemini-3.1-flash-image-preview`, stored in Emergent object storage under `house-of-monster/demo/*.jpg`, registered in `files` so `/api/files/...` serves them).
- 8 fictional artists (Kai Rivera, Yuki Tanaka, Marisol Vega, Theo Lindqvist, Amara Okafor, Dex Morrow, Inês Duarte + Demo Artist) w/ avatars, studio configs, bios; 3 collectors (Jordan, Priya, Luca). Passwords: artists `DemoArtist2026!`, collectors `DemoCollector2026!`.
- 27 artworks (live/sold/prints), 16 feed posts (WIP/sold/exhibition/auction/…), 8 auctions (3 live incl. one ending <1h, 2 scheduled, 3 ended), 5 offers, 5 commissions across all stages, 4 orders (+2 reviews), 10 events (paid rooftop show w/ 8 tickets, full battle w/ waitlist, 4-part weekly series, past checked-in open studio…), DMs, follows, likes, comments, saves, notifications for both demo protagonists.
- `--wipe-tests` deleted ~210 junk accounts from earlier automated runs (domains @test.com/@t.com/@t.io/@x.com/@test.io/@example.com) + orphans. Real user accounts untouched.

### Attendee Broadcast
- `POST /api/events/{id}/broadcast` (host/admin) `{subject, message, via_dm, via_email, include_waitlist}` → DMs (via new `messages.deliver_dm()` helper), Resend email (`event_broadcast_html`), push + in-app notification (`event_broadcast`) to every non-refunded RSVP (+ waitlist optional), delivered concurrently via `asyncio.gather`. History stored in `event_broadcasts`, `GET /api/events/{id}/broadcasts`.
- Frontend: `components/events/BroadcastModal.js` — opened from **Message attendees** button in host sidebar; channel toggles, sent history.

### Waitlist Position Email
- `join_waitlist` now emails `waitlist_position_html` ("You're #N") + inserts `event_waitlist_joined` notification with `position`.

### Series-level Reminders Toggle
- `reminders_enabled` (default true) on events; settable at create (`event-reminders` checkbox), in Edit modal (`edit-reminders`, respects apply_to=series), and via one-tap **Reminders on/off · series** sidebar button (`reminders-toggle-btn`). `check_event_reminders()` skips events with `reminders_enabled == False`.

### Misc
- Event modals bumped to `z-[1200]` (Leaflet panes were bleeding through the backdrop).
- Refund code in `_cancel_single_event` de-tangled; CSV media type now `text/csv; charset=utf-8`.
- New notification kinds in `Notifications.js`: event_waitlist_joined, event_waitlist_open, event_broadcast.

### Testing — iteration_13: 33/33 backend + 100% frontend (first automated pass over the whole Events/Ticketing system). `/app/backend/tests/test_iter13_events_broadcast_waitlist.py`.

### ⚠️ DNS still pending (BLOCKING all customer emails)
Resend domain `artcorestudio.net` status = `not_started`. Sandbox only delivers to the account owner's inbox, so receipts/refunds/waitlist/broadcast emails currently fail for everyone else. Records to add at the registrar (from Resend):
- TXT `resend._domainkey` → `p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCrbwb3RNufXiQzWnJJXaEHWq0Atvdz…` (copy full value from Resend)
- CNAME `send` → `send.forge.rmta.net`
- CNAME `rsend` → `rsend.forge.rmta.net`
Then click Verify in Resend → Domains.

### Competition punch list → `/app/memory/COMPETITION_PUNCHLIST.md`

- Go to Resend → Domains → Add `artcorestudio.net`.
- Add 3 DNS records at your registrar:
  - **TXT** at root: `v=spf1 include:_spf.resend.com ~all`
  - **CNAME** at `resend._domainkey`: value provided in Resend
  - **MX** at `send`: value provided in Resend (priority 10)
- Wait ~5 min for propagation, click Verify in Resend.
- Once verified, refund + ticket emails will send from `refunds@artcorestudio.net` instead of falling back to sandbox `onboarding@resend.dev`.



## Series Edit + Auto-Charge + CSV + Demo Logins (Mar 4, 2026)

### Series Editing
- `PATCH /events/{id}` accepts `apply_to: "this" | "series"` alongside any editable fields (title, description, category, location, start/end, capacity, is_free, ticket_price).
- When `apply_to=series`, every future non-cancelled sibling is updated in one call. Individual `start_at/end_at` never change for series edits (each occurrence keeps its own date).
- Frontend: `EditEventModal` opened from a new **Edit event** button in the host sidebar. Shows a radio pair — "This occurrence only" / "Entire series" — when the event is part of a series.
- 403 for non-host verified.

### Waitlist Auto-Charge (paid events)
- When a paid RSVP is refunded or a hold expires, `_promote_from_waitlist()` now:
  - For **paid** events: creates a Stripe Checkout Session with `expires_at = now + 15min`, stores a `waitlist_holds` record + a `payment_transactions` row (kind=event_ticket, waitlist_hold=true), and sends the buyer a push + email with the direct checkout link.
  - For **free** events: sends the plain invite (unchanged).
- New `_sweep_expired_holds()` runs opportunistically on `GET /events` — expires stale holds, marks tx as `expired`, and re-promotes the next waitlist user.
- `_apply_paid()` marks the hold as `claimed` when the buyer completes checkout.
- Email template updated with amber countdown warning "⏱ Your seat is held for 15 minutes."

### Analytics CSV Export
- New `GET /events/{id}/analytics.csv?kind=attendees|revenue` — host/admin only, returns `text/csv` with attachment disposition.
- **Attendees CSV**: Name, Email, RSVP Date, Paid, Amount, Refunded, Checked In, Checked In At.
- **Revenue CSV**: Transaction ID, Buyer Email, Amount, Currency, Status, Payment Intent, Refunded, Date.
- Analytics modal has two new pill buttons **CSV · Attendees** and **CSV · Revenue** in the header — one click downloads.

### Demo Accounts + One-Tap Login
- Seeded at backend startup:
  - Demo Artist: `demo.artist@artcorestudio.net` / `DemoArtist2026!`
  - Demo Collector: `demo.collector@artcorestudio.net` / `DemoCollector2026!`
- `/login` page redesigned with a **ONE-TAP DEMO** section at the top:
  - Lime "Enter as Artist" button → auto-login → routes to `/studio`
  - Violet "Enter as Collector" button → auto-login → routes to `/dashboard`
- Divider **OR SIGN IN NORMALLY** below → regular email/password form preserved.
- `test_credentials.md` updated with all three seed accounts.

### Testing
- Backend curl: demo logins return valid tokens with correct roles; series PATCH updates 1 vs all siblings; CSV endpoints return proper text/csv with headers; non-host PATCH returns 403.
- Frontend screenshots: login page with green Artist + violet Collector one-tap buttons; auto-navigated Studio Editor showing "HEY, DEMO ARTIST."



## 2026-06 — Fee change
- Global commission changed 3% → 4% (backend defaults in admin.py/payments.py/server.py/events.py, DB settings.global, Upcycle copy). Verified via GET /api/settings.
- Answered user: 4% application fee stays in platform Stripe balance; remainder routed to artist Connect Express account via destination charge. Platform Stripe account claim URL lives in backend/.env STRIPE_ONBOARDING_URL; artists connect at /studio → Payouts.

## 2026-06 — Seller-pays-processing (all sale types)
- connect.py build_transfer_options adds on_behalf_of=seller account → Stripe processing fee debited from seller side; platform keeps full 4%.
- payments.split_amount(gross, settings) used by buyer_order/auction_win/offer_payment/commission_payment + events host analytics (also fixed settings id bug "platform"→"global"). Orders now store processing_fee.
- Settings: processing_percent (2.9), processing_fixed (0.30) editable in /admin; GET /api/settings/fee-preview?gross=X.
- Studio Payouts tab: FeePreview calculator. $100 sale → platform $4.00, Stripe $3.20, artist $92.80.
- Tested: iteration_19.json all pass.

## 2026-06 — Batch: Stripe Setup Card, Artist Analytics, Keep-More strip, Gift Tickets (iteration_20 all pass)
- Admin → Stripe tab: platform account status, claim link (STRIPE_ONBOARDING_URL), save live keys (validated against Stripe, stored in settings.global), test/live switch. stripe_config.apply_stripe_keys() runs at startup + on save; webhook secret resolved at runtime.
- Analytics: artwork_views + studio_visits collections; /studio/analytics/me now returns total_views, total_saves, top_viewed, follower_growth(8wk), visit_series(14d). AnalyticsPanel.js.
- KeepMoreStrip.js on Home (before CTA) and Onboarding step 0 (compact).
- Gift tickets: POST /api/payments/events/{id}/gift → Stripe checkout kind event_ticket_gift; _apply_gift_ticket creates rsvp {gift, gift_token, gift_email, user_id or null}, emails recipient QR (gift_ticket_html) + gifter receipt; public GET /api/events/gift/{token} + /qr.png; /gift/:token page; register() auto-claims rsvps by email.

## NEXT (user-approved): i18n core surfaces — react-i18next, navbar picker saved to profile, 8 languages (es, fr, de, pt, it, ja, ko, zh-CN). Scope: nav, home, auth, onboarding, explore filters, artwork/event CTAs, checkout, notification labels.

## 2026-06 — Batch: i18n, Flip Commissions, 2FA, Gift Reminders (iteration_21 all pass)
- i18n: react-i18next, src/i18n.js + src/locales/{en,es,fr,de,pt,it,ja,ko,zh}.json. LanguagePicker in navbar; saved to localStorage hom_lang + users.language via PATCH /auth/me. Covered: nav/footer, Home, Auth, Onboarding, KeepMoreStrip, Explore, Marketplace filters, ArtworkDetail CTAs, Cart, EventDetail CTAs, Notifications (title + kind labels via notif.* with English fallback). Rest of app still English — add keys to locales and t() calls to extend.
- Flip Commissions: commissions.kind art|flip + furniture {furniture_type, dimensions, condition, handoff dropoff|pickup|ship, city}; GET /api/commissions/flip/artists; CommissionRequestModal mode/allowFlip; FlipMyFurniture section on /upcycle; flip-details on commission page. Uses existing deposit/balance escrow.
- 2FA: backend/twofa.py (pyotp TOTP or email OTP, 8 recovery codes, 5-min challenge JWT, 8-fail lockout). Login returns requires_2fa + challenge_token; /api/auth/2fa/{status,setup,enable,disable,recovery-codes,resend,verify-login}. /security page; nav-security link; payouts tab nudge.
- Gift reminders: server startup runs check_event_reminders() every 10 min; _blast_reminder emails gift recipients (gift_reminder_html with QR) at 24h marker, idempotent via rsvp.gift_reminder_sent. Reminder emails use PUBLIC_APP_URL env (fallback artcorestudio.net).

## 2026-06 — Batch: Founding waiver + rate lock, Flip Quotes, Trusted Devices, Wallet Pass, i18n phase 3 (iterations 22-23 all pass)
- waiver.py: 0% window (30d / 5 sales, settings waiver_*), grant at artist register (email-keyed, no restart), 7d/1d reminders in server reminder loop; admin POST/DELETE /api/admin/waiver/{uid}. Founding rate lock: founding_member/founding_number/locked_commission_percent set at signup while founding_left>0 (cap 500, rate 4); effective = min(locked, global), waiver → 0. Admin /api/admin/waiver/founding/{backfill|uid}. All 35 pre-existing artists backfilled as founders. /api/settings exposes founding_* stats; fee-preview viewer-aware.
- UI: FoundingWaiver.js (FoundingBanner on landing/onboarding via KeepMoreStrip, WaiverBadge + FoundingChip on studio overview, AdminWaiverButton). Admin settings: waiver + founding inputs.
- Flip Quotes: respond(action=counter) stores quote {amount, sketch_image, note, timeline_days}; Commissions.js quote UI both sides.
- Trusted devices: verify-login remember_device → device_token (hashed, 30d, max 10); login body device_token skips 2FA; GET/DELETE /api/auth/2fa/devices; Security.js list/revoke; hom_device in localStorage.
- Wallet pass: wallet_pass.py PIL renderer (1080x1920 PNG); GET /api/events/{id}/my-ticket/pass.png (auth) + /api/events/gift/{token}/pass.png; WalletPassButton (Web Share API → download fallback) on EventDetail/Tickets/GiftTicket. NOTE: native Apple .pkpass / Google Wallet need developer signing credentials — not implemented.
- i18n: studio/orders/messages blocks in all 9 locales.
- Strategy note: recommended 4% as founding rate, standard rate to rise to 6-8% later + non-commission revenue (buyer ticket fee, boosts, Pro subscription).

## 2026-06 — Art Core Pro, Badges, Depop-style payouts (iteration_24 pass + badge fix verified)
- pro.py: Stripe Billing product art_core_pro, prices pro_monthly $12 / pro_yearly $99 (lookup keys, created at startup), coupon founding50 (50% forever) auto-applied for founding_member. /api/pro/{plans,status,checkout,cancel,resume,portal}. Webhook syncs customer.subscription.* → users.pro; invoice.payment_failed notif. Perks: boost (artworks default sort Pro first), PRO_THEMES gated 402 (luxury_gallery, neon_digital, custom), pro_active in public_user/enrich, Pro badge. /pro page, nav-pro, studio upsell + theme lock.
- Badges.js: FoundingBadge/ProBadge on ArtCard (feed + artworks enrich) and ArtistStudio header (studio.py artist object).
- Payouts (payouts.py): funds held on platform — connect.build_transfer_options returns {} (no destination charge/on_behalf_of). artist_payouts status held + release_at (sale + 10 business days; Pro 5). Buyer mark_delivered → release_at +2d (Pro: now). Sweep release_due_payouts() every 10 min → transfer_manual → transferred, else pending (manual). Tracking mandatory (ShipReq). Dashboard upcoming_payouts + payout_policy; Payouts tab Upcoming payouts. Refunds fall back when no transfer to reverse. Legacy auto_transferred statuses remain on old orders.
- Decisions: Pro $12/mo, $99/yr, founders 50% off for life. Native Wallet passes parked until Apple Pass Type ID/cert + Google Wallet issuer creds provided.

## 2026-06 — Delivery confirmation / anti-chargeback guard (iteration_25 all pass)
- backend/delivery.py: pipeline pending → shipped → carrier_delivered → delivered | not_received. Seller `POST /api/orders/{id}/carrier-delivered` (needs shipped + tracking) or sweep estimates delivery 7d after shipped_at (`carrier_delivered_source: estimated`). `confirm_deadline` = +3 days → sweep auto-confirms (`confirmed_how: auto`). Buyer `POST /confirm-received` (payout release_at +2d / Pro now), `POST /not-received` (payout frozen: release_at null, hold_reason not_received; dispute auto-opened reason not_received with `tracking_proof`, seller `order_not_received` + admins notified). `GET /api/orders/confirmations/pending` drives the modal. Buyer notified in-app + push + email (`delivery_confirm_html`) when carrier-delivered.
- payouts.py: freeze_payouts / unfreeze_payouts. disputes.py: any open dispute freezes payouts; admin reject → unfreeze + order delivered (`confirmed_how: admin_dispute_rejected`). Sweep runs in server _reminder_loop every 10 min.
- Frontend: `components/orders/DeliveryConfirmModal.js` mounted in Layout — full-screen z-5000, no close, Escape/backdrop blocked, body scroll locked, polls on route change + 60s + window focus; two buttons + 2-step confirm for not-received. Orders.js: new statuses (carrier_delivered / not_received), seller "Tracking shows delivered" button, buyer received/not-received buttons, seller awaiting note. Admin DisputesPanel shows tracking proof. Notification kinds: order_delivered_confirm, order_received_confirmed, order_auto_confirmed, order_not_received.
- NOT integrated: real carrier tracking API (EasyPost/AfterShip/Shippo) — seller manual tap + 7-day estimate for now.

## 2026-06 — Code review fixes
- Real bug fixed: social.py used `_pro_active` outside its `if artist:` guard (crash when artist deleted) — now top-level import + guarded (2 sites).
- delivery↔orders cycle removed: legacy `/orders/{id}/mark-delivered` route moved into delivery.py as an alias of `/confirm-received`; delivery imports `_enrich_order` one-way. auth→waiver remains a deliberate lazy import inside `register()` (waiver needs auth's Depends at import time).
- studio.py `__import__("auth")` → static import; artworks.py ETag md5 → sha256; test fixture fake device token labelled as non-secret. waiver.py `is None` comparisons are correct (false positive).
- Security audit (read-only) open items: SEC-001 hard-coded admin/demo passwords in server.py seed (move to env + rotate), SEC-002 CSV formula escaping in events.py analytics export, SEC-003 html.escape user values in emails.py; P3: login/OTP rate limits, pinned CORS, 2FA lockout decay.

## 2026-06 — Security hardening + EasyPost live tracking (iteration_26: 19/19 backend + frontend pass)
- SEC-001 fixed: admin + demo credentials live only in backend/.env (ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_ARTIST_PASSWORD, DEMO_COLLECTOR_PASSWORD). Startup re-syncs hashes → change the env value to rotate. Admin password rotated to a random 24-char value (see memory/test_credentials.md). Demo one-tap buttons call `POST /api/auth/demo-login {role}`; no passwords in the client bundle. seed_demo.py + all tests read passwords from env (tests/conftest.py loads .env).
- SEC-002 fixed: events analytics CSV uses `_SafeWriter` (quote-prefixes cells starting with = + - @ tab CR).
- SEC-003 fixed: `@_escaped` decorator on all 9 email templates (html.escape of every str arg incl. dict values); event_broadcast_html already escaped.
- Rate limiting (backend/ratelimit.py, Mongo `rate_limits` w/ TTL): login 10 fails/email + 30 fails/IP per 15 min → 429 + Retry-After; success clears email counter; demo-login 30/IP; OTP resend 3/10 min; 2FA lockout (8 fails) decays after 15 min via `twofa_fail_at`.
- Live tracking (backend/tracking.py, `easypost` SDK): when EASYPOST_API_KEY set → Tracker created at ship time (orders.ship_order → start_tracking, carrier normalised via CARRIER_MAP, non-fatal), `POST /api/tracking/easypost/webhook` (HMAC via easypost.util.validate_webhook, dedupe in `webhook_events`) + 30-min poll fallback in server loop → delivered ⇒ delivery.mark_carrier_delivered(source "carrier:webhook|poll"). 7-day estimate sweep skips orders with a tracker. `GET /api/tracking/config`, `GET /api/orders/{id}/tracking` (refreshes tracker on demand). Frontend `LiveTrackingPanel` on OrderDetail (status chip, event timeline, carrier link; "Manual tracking" when key absent). **Currently MANUAL mode — user has not supplied an EasyPost key.** To enable: set EASYPOST_API_KEY + EASYPOST_WEBHOOK_SECRET, register webhook URL `{backend}/api/tracking/easypost/webhook` in EasyPost dashboard, restart backend.
- Still open (P3): pinned CORS origins (CORS_ORIGINS env already supported), private-asset access checks on /api/files, Stripe live key encryption at rest.

## 2026-06 — Launch prep: Legal pages + demo toggle
- `pages/Legal.js` at `/legal/:doc` (terms | privacy | refunds) with tab nav; footer links (footer-terms/privacy/refunds). Terms §2 is the user-requested prohibited-items / package-contents disclaimer (drugs, weapons, anything not the listed artwork → seller/buyer solely liable; Art Core never handles packages; indemnity; cooperation with law enforcement). §3 codifies mandatory tracking + 3-day deemed-confirmation. Refund policy mirrors the dispute flow. Disclaimer footer: have an attorney review. Contact email placeholder legal@artcorestudio.net.
- Register form: required 18+/Terms/Privacy/Refunds consent checkbox (register-consent-input) — submit disabled until checked.
- Demo one-tap buttons gated by `settings.global.demo_login_enabled` (default true): exposed in GET /api/settings, admin toggle in /admin Settings ("Demo sign-in buttons", demo-login-enabled-input), `/api/auth/demo-login` → 403 when off. **Turn OFF before public launch.**
- Launch checklist given to user: Stripe live mode, Resend DNS, deploy + custom domain (support_agent steps), real founder content, disable demo buttons.

## 2026-06 — Launch page, private files, security re-audit fixes (iteration_27: 12/12 backend + all frontend pass)
- `/launch/:id` (LaunchPage.js): event landing with hero, when/where, CTA (logged-out → `/register?next=`; logged-in → RSVP/ticket → /tickets), Share, flyer poster download. `GET /api/events/{id}/poster.png` (poster.py, 1080×1620 Pillow, QR → launch URL). Auth.js honours `?next=`.
- Private files: `files.private` + `scope` ({kind:order,order_id} | {kind:thread,users}) set by disputes.open_dispute and messages.deliver_dm (image attachments must reference a real upload → 400 otherwise). `GET /api/files/{path}` for private → needs authorized JWT header (buyer/seller/thread member/uploader/admin) OR short-lived (15 min) HMAC signed link `?exp=&sig=` minted by `artworks.sign_file_url` — returned as `disputes.image_urls[]` and `attachment.signed_url`. No account JWT in URLs. Private responses: `Cache-Control: private, no-store`, `Referrer-Policy: no-referrer`.
- Security re-audit fixes: `/events/{id}/attendees` now auth-required, minimal shape for non-hosts (host/admin get email/paid/amount/checked_in); `public_user()` drops email unless `include_email=True` (/me, login, admin list); `_waitlist_invite_html` escaped; rate-limit IP uses last X-Forwarded-For hop.
- Remaining P3: pin CORS via `CORS_ORIGINS` at deploy; dependency CVE scan; Stripe live key encryption at rest.
- PayPal: user requested then CANCELLED — not implemented.

## 2026-06 — Clean slate
- Admin email → admin@artcorestudio.net (env ADMIN_EMAIL). Full data wipe: all non-admin users + all content collections deleted; files soft-deleted; admin profile reset (avatar/cover/bio/stripe fields). `demo_login_enabled=false`; server.py seeds demo accounts only when the toggle is on. Dev-overlay fix: index.html ignores anonymous cross-origin 'Script error.' events (real errors still surface).

## 2026-06 — Onboarding without a tour (iteration_28: 9/9 backend + all frontend pass)
- `GET /api/studio/setup-checklist` (+ `POST …/{shared|dismiss|restore}`) — 5 steps: profile (avatar + bio≥20), artwork (count>0), payouts (stripe_connect_status pending/active), publish (published_at + artwork), share (users.checklist_shared). Defined BEFORE `/{artist_id}` in studio.py. `users.checklist_dismissed`.
- `components/studio/SetupChecklist.js` mounted in StudioEditor above tabs (progress bar, tab-switching items, dismiss). StudioEditor honours `?tab=` deep link.
- `components/EmptyState.js` (icon/title/body/cta/secondary) used on: Studio artworks, Orders, Selling, Messages, Tickets, Saved, Feed, Explore.
- Cart: escrow note (escrow-note) + test-card hint only when `settings.stripe_mode==='test'` (`/api/settings` now returns stripe_mode). Cart NaN guard for items without a price.
- `/how-it-works` (HowItWorks.js): collectors 3 steps, artists 3 steps, live fee example from settings ($100→$92.80), more-than-a-shop, FAQ, CTAs. Linked from Home hero (hero-how-it-works) + footer (footer-how-it-works).
- Throwaway artist for testing: tut.artist@example.com / TutArtist123!

## 2026-06 — Admin tools, Listing Assistant, avatar, 12% commission (iterations 29–31 all pass)
- **Dispute safety valve** (backend/admin_tools.py): sweep every 10 min; disputes unreviewed for `settings.dispute_auto_days` (default 7, admin-editable 2–30) auto-resolve via disputes.resolve(): not_received + carrier/seller/admin-confirmed tracking → reject (payout unfrozen); else refund_full. Admin warned 2 days before (`dispute_auto_warning`), failures recorded (`auto_resolve_error`) + `dispute_auto_failed`. Manual: POST /api/admin/disputes/sweep.
- **Data export**: GET /api/admin/export.zip (json of all collections w/ users scrubbed + users/orders/payouts/transactions CSV, formula-safe). Admin Settings → “Download full backup”.
- **Reset to clean slate**: POST /api/admin/reset-to-clean-slate {confirm:"DELETE EVERYTHING"} — deletes all non-admin users + content; keeps settings/Stripe/admins; clears admin founding/waiver fields. Admin Settings → Danger zone. Run after any testing session (testing agents create founders!). DB currently: 1 admin, 0 founders.
- **Claude Listing Assistant** (backend/listing_assist.py, claude-sonnet-4-6 vision via emergentintegrations ImageContent): POST /api/studio/listing-assist {image_path, section, hints, width_in, height_in, kind} → title/description/medium/style/color/tags/price_low/high/suggested/note (+furniture_type/materials for upcycle). UI: components/studio/ListingAssistant.js under Images on /studio/upload; “Use this draft” fills the form. ~10–20s.
- **Artist photo**: StoryEditor avatar editor (upload/change/remove → PATCH /auth/me avatar); ArtistStudio header shows avatar. PATCH /auth/me now uses exclude_unset so null clears fields.
- **Fees**: commission_percent = 12 (settings). Founding Artists locked 4% for life (founding_rate 4, cap 500), 30-day / 5-sale 0% waiver unchanged. KeepMoreStrip + keep.body i18n ({{pct}}) + HowItWorks read live settings (~85% keep; $100 → $84.80).
- Referral idea agreed in principle (not built): invitee's first sale → referrer's next sale fee-free + badges (no free month).

## 2026-06 — Referral Rewards (iteration_32: 12/12 backend + frontend pass)
- backend/referrals.py: `users.referral_code` (6-char, lazily minted), `referred_by` (artists only), `on_first_sale` fires once via waiver.after_sale (called from all 4 payment paths) → referrer `fee_free_sales += 1`, `referral_conversions`; invitee `referral_converted_at`. effective_rate: waiver > fee_free credit (0%, `fee_free_referral`) > founding lock > global. Credit consumed by `consume_fee_free_sale`. Badges `recruiter`/`crew` (growth.py). Notifications referral_joined / referral_reward / referral_badge. Endpoints GET /api/referrals/me, GET /api/referrals/check/{code}. Register accepts `referral_code`.
- Frontend: ReferralCard in Studio → Payouts; /register?ref=CODE banner (+ localStorage hom_ref). Links use PUBLIC_APP_URL (prod domain) — in preview they point to artcorestudio.net (expected).
- Campus Pages explained to user (not built): school field on users/events + /campus/{slug} page.
- EasyPost key still not provided → tracking in manual mode.

## 2026-06 — Campus Pages (iteration_33: 17/17 backend + frontend pass)
- backend/campus.py + campus_seed.py (~300 art schools worldwide + ALIASES like RISD/SCAD/CSM; seeded idempotently at startup, `db.campuses` {id, slug, name, norm, city, country, status approved|pending|rejected|merged, featured, seeded, created_by, merged_into}). Users get denormalised `campus_id/campus_slug/campus_name`; `public_user()` + studio artist + artworks artist enrich expose `campus`.
- Public: GET /api/campus/search?q= (name/city/alias), GET /api/campus (directory: campuses with artists or featured), GET/POST/DELETE /api/campus/me (artist picks by id/slug or types a new name → pending campus + admin `campus_pending` notif), GET /api/campus/{slug} (artists w/ works/followers/sales, live artworks, upcoming events tagged or hosted by campus artists, leaderboard, stats; follows merge chain).
- Admin: GET /api/admin/campuses?status&q, PATCH /api/admin/campuses/{id} {status, featured, name, city, country} (approve → `campus_approved` notif to creator; reject → untags artists; rename syncs denorm), POST /api/admin/campuses/{id}/merge {into_id}.
- Events: `campus_id` on create/update; GET /api/events?campus=slug filter; stored campus_slug/campus_name.
- Frontend: pages/Campus.js (/campus directory + /campus/:slug), components/SchoolPicker.js (search combobox + "Add … as my school"), studio/MySchoolCard.js in Studio → Story, admin/CampusesPanel.js (Admin tab "Campuses", /admin?tab= deep link), CreateEventModal campus picker (event-school-*), ArtistStudio header chip (studio-campus-chip), footer "Campus pages", Artists page "Browse by art school". Notifications: campus_pending → /admin?tab=campuses, campus_approved → /campus/slug.
- Not built (offered): campus ambassador role, .edu verified-student badge, US College Scorecard API source.
- EasyPost: user tried to sign up but is stuck on EasyPost's account verification; key still not provided → tracking remains in manual/7-day-estimate mode.
