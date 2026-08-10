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
- `/api/auth/*` — register, login, me, patch me
- `/api/upload/image` + `/api/files/{path}` — Emergent object storage
- `/api/artworks` — CRUD + filters, aotw endpoints
- `/api/artists` + `/api/artists/{id}` — portfolios
- `/api/payments/checkout` — Stripe buyer checkout
- `/api/payments/upload-fee` — Stripe artist fee
- `/api/payments/status/{sid}` + `/api/stripe/webhook`
- `/api/admin/*` — settings, featured, aotw, orders, mentorship, stats, artists
- `/api/artist/*` — dashboard, connect/start, connect/complete
- `/api/users/{id}/follow` + `/social` — social graph
- `/api/artworks/{id}/like` + `/likes` — likes
- `/api/artworks/{id}/comments` + delete — comments
- `/api/messages/*` — DMs (threads, thread/{id}, send, unread-count)
- `/api/search` — artworks + artists
- `/api/feed` — explore feed with enrichment
- `/api/newsletter` — public signup
- Admin auto-seeded on startup: monster@houseofmonster.com

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
