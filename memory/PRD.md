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

## Demo World + Attendee Broadcast + Waitlist Emails + Series Reminders (Mar 5, 2026)

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


