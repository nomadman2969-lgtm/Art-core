# Art Core

**The social marketplace built for artists.** Virtual studios, escrow-protected sales, live auctions, commissions, upcycled furniture, ticketed events and campus pages — in one dark, editorial, mobile-first app.

Live: [artcorestudio.net](https://artcorestudio.net)

---

## What's inside

| Area | Highlights |
|---|---|
| **Virtual Studios** | Themed, drag-and-drop artist storefronts (7 themes, textures, sections, AI studio designer, Claude "Polish" copywriting) |
| **Marketplace** | Originals + upcycled furniture, offers, saves/collections, follows, likes, comments, DMs with attachments |
| **Escrow payouts** | Stripe Connect. Funds held on-platform; released 2 days after the collector confirms delivery (mandatory tracking, un-dismissible confirm modal, 7-day dispute safety valve) |
| **Live auctions** | Real-time bidding over WebSockets, auto-extend, payment deadlines, forfeits |
| **Commissions** | Briefs, counter-offers, deposits, flip-my-furniture quotes with sketches |
| **Events** | Physical + virtual events with map, RSVPs, paid tickets, waitlists w/ 15-min holds, QR check-in, gift tickets, wallet-pass PNG, reminders, host broadcasts |
| **Campus Pages** | Artists tag their art school (300+ seeded, aliases like RISD/SCAD) → auto-generated `/campus/{slug}` pages with artists, work, events, leaderboard; admin approve / feature / merge |
| **Growth** | Founding Artist 4% lifetime rate lock, 0% first-30-days waiver, artist-to-artist referral rewards, achievement badges, Art Core Pro subscription, staff picks, rankings |
| **Trust & safety** | 2FA (TOTP / email) + trusted devices, rate-limited auth, signed private file URLs, reports & moderation, disputes with tracking proof, legal pages |
| **Admin Command Desk** | Fees, Stripe setup, curation, refunds, disputes, reports, waivers, campuses, full data export (ZIP), clean-slate reset |
| **i18n** | 9 languages (en, es, fr, de, pt, it, ja, ko, zh) |

Fees as configured: **12%** platform commission (seller pays card processing) · Founding Artists locked at **4% for life** · new artists **0%** for 30 days / 5 sales.

---

## Stack

- **Frontend** — React 18 (CRA + CRACO), Tailwind CSS, shadcn/ui, react-router, react-i18next, Leaflet, sonner
- **Backend** — FastAPI (Python 3.11, async), Motor (MongoDB), PyJWT + bcrypt, WebSockets
- **Data** — MongoDB
- **Integrations** — Stripe (Payments, Connect, Billing, webhooks), Resend (email), EasyPost (carrier tracking, optional), Web Push (VAPID), Claude via `emergentintegrations` (listing assistant, studio designer, copy polish)

```
/backend      FastAPI app — one module per domain (auth, artworks, payments, payouts, delivery, events, campus, …)
/frontend     React app — src/pages, src/components, src/locales
/memory       Product docs: PRD.md, MASTER_PROMPT.md (full spec)
/test_reports Test iteration reports
```

---

## Quick start (local)

### Prerequisites
- Python 3.11+, Node 18+ with **yarn**, MongoDB 6+ running locally (or an Atlas URI)

### 1. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
cp .env.example .env          # fill in values — see "Environment" below
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
The API is served under `/api` (e.g. `http://localhost:8001/api/settings`).

### 2. Frontend
```bash
cd frontend
yarn install
cp .env.example .env          # REACT_APP_BACKEND_URL=http://localhost:8001
yarn start                    # http://localhost:3000
```

### 3. First login
On boot the backend seeds one admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD` (the hash is re-synced every start, so rotate by changing the env value). Sign in, open **/admin → Stripe** to paste keys, then **Settings** to review fees.

---

## Environment

Never commit `.env` files (they are git-ignored). Copy the examples and fill them in.

### `backend/.env`
| Key | Required | Notes |
|---|---|---|
| `MONGO_URL` | ✅ | e.g. `mongodb://localhost:27017` |
| `DB_NAME` | ✅ | database name |
| `JWT_SECRET` | ✅ | long random string |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | ✅ | seeded founder account |
| `CORS_ORIGINS` | ✅ | comma-separated allowed origins |
| `PUBLIC_APP_URL` | ✅ | public site URL used in emails/QRs/referral links |
| `STRIPE_SECRET_KEY` | ✅ | must be present at boot (a `sk_test_…` key is fine); live keys can be set from **/admin → Stripe** |
| `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_MODE` | for commerce | can also be set from **/admin → Stripe** |
| `RESEND_API_KEY`, `SENDER_EMAIL` | for email | verify your domain's DNS in Resend |
| `EMERGENT_LLM_KEY` | for AI features | listing assistant, studio designer, polish |
| `EASYPOST_API_KEY`, `EASYPOST_WEBHOOK_SECRET` | optional | enables live carrier tracking; otherwise 7-day estimate |
| `DEMO_ARTIST_PASSWORD`, `DEMO_COLLECTOR_PASSWORD` | optional | demo accounts, only seeded when `demo_login_enabled` is on and the password is set |

### `frontend/.env`
| Key | Notes |
|---|---|
| `REACT_APP_BACKEND_URL` | backend origin without trailing slash; all calls go to `${URL}/api/...` |

---

## Stripe webhooks

Point a Stripe webhook at `POST {backend}/api/stripe/webhook` and subscribe to `checkout.session.completed`, `payment_intent.*`, `charge.refunded`, `customer.subscription.*`, `invoice.payment_failed`, `account.updated`. For local dev: `stripe listen --forward-to localhost:8001/api/stripe/webhook`.

EasyPost (optional): register `POST {backend}/api/tracking/easypost/webhook` in the EasyPost dashboard.

---

## Tests

```bash
cd backend
pytest                        # runs the API suites in backend/tests (needs a running backend + .env)
```
Frontend flows are exercised with Playwright by the QA reports in `/test_reports`.

---

## Deployment notes

- Backend must run on a single origin behind HTTPS; all routes are prefixed with `/api` so the frontend and API can share a domain.
- Set `CORS_ORIGINS` to your real domains before launch.
- Turn off **Demo sign-in buttons** and switch Stripe to live mode in `/admin → Settings` / `/admin → Stripe`.
- Run **Download full backup** before any **Reset to clean slate**.

---

## Product docs

- [`memory/MASTER_PROMPT.md`](memory/MASTER_PROMPT.md) — complete spec: personas, business rules, data model, design system
- [`memory/PRD.md`](memory/PRD.md) — changelog of everything shipped

## License

Proprietary — © Art Core. All rights reserved. See [LICENSE](LICENSE).
