# Art Core — Competition Punch List (priority order)

## Tier 1 — Must do before submitting (stability + first impression)
1. **Full E2E test pass + fix every red.** Run testing_agent across Events/Ticketing, Auctions, Offers, Commissions, DMs, Studio. Crashes cost more than features earn.
2. **Mobile polish pass.** Judges will open it on a phone. Check: nav overflow, feed cards, event detail, QR ticket modal, auction bid input, studio editor (read-only on mobile is fine).
3. **Verify Resend DNS** (3 records at registrar) so receipts come from `refunds@artcorestudio.net`, not a sandbox sender.
4. **Demo script (90 sec).** One-tap Collector → Feed (trending event + WIP post) → bid on Chrome Heart (ending soon) → Tickets wallet QR → DM thread. One-tap Artist → Studio editor theme swap → analytics → door check-in scan. Rehearse it.
5. **Empty/error states.** Every list page needs a designed empty state, and API failures need toasts, not silent blanks.

## Tier 2 — Strong differentiators judges will remember
6. **WebSockets for auctions + DMs** (replace 5s polling). Live bid ticks and instant typing indicators make the "real-time" claim visibly true.
7. **Trust & safety mini-suite:** order dispute flow (buyer opens → admin resolves → refund), report artwork/user, admin moderation queue. Answers the inevitable "what if the painting arrives damaged?" question.
8. **Provenance / Certificate of Authenticity** — generated PDF per sold original with artwork image, dimensions, artist signature block, order id, QR back to the artwork page. Cheap to build, huge perceived value.
9. **Studio share cards** — OG image per studio/artwork so links look great on Instagram/X. Artists share → growth loop.
10. **Onboarding flow for new artists** — 3 steps: pick a theme → upload first piece → publish studio. Currently new users land on an empty studio.

## Tier 3 — Narrative + polish
11. **Sharpen the pitch:** "The only place an artist can sell an original, auction a study, and ticket their own opening — from one studio page." Put it on the Home hero.
12. **Founder story page** with real content (currently placeholder).
13. **Rankings/gamification** — badges for first sale, sold-out show, 100 followers. Visible on studio header.
14. **Accessibility sweep** — focus rings, alt text on artwork images (use title), contrast on lime-on-white buttons.
15. **Performance** — lazy-load artwork images, thumbnail variants (400px) for grids; current generated images are ~300 KB each.
16. **Get 5–10 real artists posting** before the deadline. Even tiny real traction beats any feature.

## Already strong — lead with these
- Virtual Studio (themes, textures, drag-drop, draft→publish, AI polish)
- Full commerce loop with Stripe Connect payouts and auto-refunds
- Events: map, paid tickets, QR check-in, waitlist auto-charge holds, series, analytics CSV
- One-tap demo logins into a lived-in demo world
