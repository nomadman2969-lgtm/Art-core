import React, { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { Scale, ShieldCheck, RotateCcw } from "lucide-react";

const EFFECTIVE = "June 1, 2026";
const CONTACT = "legal@artcorestudio.net";

const Section = ({ id, title, children }) => (
  <section id={id} className="mt-10" data-testid={`legal-section-${id}`}>
    <h2 className="font-unbounded text-lg md:text-xl font-semibold text-white">{title}</h2>
    <div className="mt-3 space-y-3 text-sm text-zinc-300 leading-relaxed">{children}</div>
  </section>
);

const Callout = ({ children }) => (
  <div className="border border-[#FF4D4D]/40 bg-[#FF4D4D]/5 rounded-sm p-4 text-sm text-zinc-200 leading-relaxed">{children}</div>
);

function Terms() {
  return (
    <>
      <p className="text-sm text-zinc-400">These Terms of Service ("Terms") govern your use of Art Core (the "Platform"), operated by Art Core Studio ("Art Core", "we", "us"). By creating an account, listing, buying, bidding, commissioning, hosting or attending an event, or otherwise using the Platform, you agree to these Terms. If you do not agree, do not use the Platform.</p>

      <Section id="marketplace" title="1. Art Core is a venue, not a seller or shipper">
        <p>Art Core is an online marketplace and community that connects independent artists ("Sellers") with buyers and collectors ("Buyers"). <strong className="text-white">Art Core does not create, own, inspect, store, pack, ship, or deliver any item listed on the Platform.</strong> Every sale is a contract directly between the Seller and the Buyer. Art Core is not a party to that contract and is not a carrier, shipper, freight forwarder, customs broker, or agent of either party.</p>
        <p>Sellers are solely responsible for the accuracy of their listings, the legality and condition of the items they sell, packaging, and handing the package to a carrier with a valid tracking number. Buyers are solely responsible for confirming receipt and inspecting items on arrival.</p>
      </Section>

      <Section id="prohibited" title="2. Prohibited items and shipping-contents disclaimer">
        <Callout>
          <strong className="text-[#FF4D4D]">Art Core has no knowledge of, control over, or responsibility for the physical contents of any package.</strong> We never see, handle, open, or inspect shipments. You may not use the Platform, or any package sent in connection with a Platform transaction, to send, sell, conceal, or transport anything other than the artwork or item described in the listing.
        </Callout>
        <p>Strictly prohibited, without limitation: controlled substances, narcotics, cannabis or cannabis products (regardless of local legality), prescription drugs, drug paraphernalia, weapons, firearms or firearm parts, ammunition, explosives, hazardous or flammable materials, counterfeit or stolen goods, currency, items that infringe intellectual-property rights, live animals, human remains, and any item whose sale, possession, or shipment is illegal under applicable federal, state, local, or international law.</p>
        <p>If a Seller includes anything in a package that is not the listed artwork — or if a Buyer requests it — <strong className="text-white">that person alone is responsible</strong>, civilly and criminally. To the fullest extent permitted by law, <strong className="text-white">Art Core, its founder, officers, employees, contractors, and affiliates are not liable</strong> for any package contents, for any loss, seizure, damage, injury, fine, penalty, prosecution, or claim arising from package contents, or for any act or omission of a Seller, Buyer, or carrier. Each user agrees to indemnify, defend, and hold Art Core harmless from any claim, investigation, demand, loss, or expense (including reasonable attorneys' fees) arising from what they ship, receive, or request.</p>
        <p>We cooperate fully with law enforcement. Accounts that violate this section are terminated immediately, pending payouts are frozen and may be forfeited, and we may report the conduct to the appropriate authorities.</p>
      </Section>

      <Section id="fulfillment" title="3. Shipping, tracking, and delivery confirmation">
        <p>Sellers must ship within the timeframe stated in the listing (or 7 days if none) and must enter the carrier and a valid tracking number on the Platform. An order cannot be marked shipped without tracking. Sellers choose their own carrier, packaging, and insurance; risk of loss in transit is allocated between Seller and Buyer according to the carrier's terms and applicable law, not by Art Core.</p>
        <p>When tracking shows the package as delivered, the Buyer is required to confirm on the Platform that the item was <em>received</em> or <em>not received</em>. If the Buyer does not respond within 3 days, delivery is deemed confirmed. A "not received" report opens a dispute reviewed by Art Core; the Seller's payout is frozen while the review is pending. Art Core's dispute decisions are made in good faith on the evidence available (including tracking data) and are final as between the parties on the Platform, without prejudice to any rights either party may have against the carrier or each other.</p>
      </Section>

      <Section id="payments" title="4. Payments, fees, and payouts">
        <p>Payments are processed by Stripe. Art Core collects the purchase price from the Buyer and holds Seller proceeds until delivery is confirmed (or deemed confirmed), then transfers the proceeds to the Seller's connected Stripe account, less the Art Core platform fee and payment-processing fees, which are borne by the Seller. Current fees are shown at checkout and in the Seller's studio and may change with notice. Founding Artists' locked rates and 0%-fee windows are honored as described at signup. Art Core Pro is a recurring subscription billed by Stripe and cancellable at any time; access continues to the end of the paid period.</p>
        <p>Auction bids, accepted offers, and accepted commission quotes are binding. Failure to pay within the stated window may forfeit the item to the next bidder and result in account restrictions.</p>
      </Section>

      <Section id="events" title="5. Events and tickets">
        <p>Events are organized by their hosts, not by Art Core. Hosts are responsible for venue, safety, permits, age restrictions, and the accuracy of event listings. Tickets are issued as QR codes and are non-transferable except through Platform gifting. If a host cancels an event, paid tickets are refunded automatically. Art Core is not liable for anything that occurs at an event.</p>
      </Section>

      <Section id="content" title="6. Your content and conduct">
        <p>You keep ownership of what you upload but grant Art Core a worldwide, non-exclusive, royalty-free license to display, reproduce, and promote it on and off the Platform for as long as it is posted. You represent that you own or have the rights to everything you post and that it does not infringe anyone else's rights. No harassment, hate, spam, fraud, fake bids or reviews, manipulation of rankings, scraping, reverse-engineering, or circumventing fees by completing Platform-originated sales off-Platform.</p>
        <p>You must be at least 18 years old (or the age of majority where you live) to sell, bid, or host. You are responsible for keeping your credentials secure; we recommend enabling two-factor authentication.</p>
      </Section>

      <Section id="ip" title="7. Intellectual property and takedowns">
        <p>To report infringing content, email {CONTACT} with the work, the infringing URL, your contact details, and a good-faith statement. We remove content that violates rights or these Terms and terminate repeat infringers.</p>
      </Section>

      <Section id="disclaimer" title="8. Disclaimers">
        <p>THE PLATFORM IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. ART CORE DOES NOT GUARANTEE THE AUTHENTICITY, QUALITY, SAFETY, LEGALITY, OR DESCRIPTION OF ANY ITEM, THE TRUTH OF ANY LISTING, OR THAT ANY BUYER OR SELLER WILL COMPLETE A TRANSACTION. CERTIFICATES OF AUTHENTICITY ARE GENERATED FROM SELLER-SUPPLIED INFORMATION.</p>
      </Section>

      <Section id="liability" title="9. Limitation of liability">
        <p>TO THE MAXIMUM EXTENT PERMITTED BY LAW, ART CORE AND ITS FOUNDER, OFFICERS, EMPLOYEES, CONTRACTORS, AND AFFILIATES WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR FOR ANY LOSS OF PROFITS, DATA, GOODWILL, OR ITEMS IN TRANSIT, ARISING FROM YOUR USE OF THE PLATFORM, ANY TRANSACTION, ANY SHIPMENT OR ITS CONTENTS, OR ANY EVENT. OUR TOTAL LIABILITY FOR ANY CLAIM IS LIMITED TO THE PLATFORM FEES YOU PAID TO ART CORE IN THE 12 MONTHS BEFORE THE CLAIM, OR $100, WHICHEVER IS GREATER. SOME JURISDICTIONS DO NOT ALLOW CERTAIN LIMITATIONS; IN THAT CASE THESE APPLY TO THE FULLEST EXTENT PERMITTED.</p>
      </Section>

      <Section id="indemnity" title="10. Indemnification">
        <p>You agree to indemnify, defend, and hold harmless Art Core and its founder, officers, employees, contractors, and affiliates from any claim, liability, damage, loss, fine, or expense (including reasonable attorneys' fees) arising from your content, your listings, anything you ship or receive, your participation in events, your violation of these Terms, or your violation of any law or third-party right.</p>
      </Section>

      <Section id="termination" title="11. Suspension and termination">
        <p>We may suspend or terminate accounts, remove content, freeze or forfeit payouts, and cancel transactions at our discretion for violations of these Terms, suspected fraud, chargeback abuse, legal risk, or to protect users. You may close your account at any time; obligations already incurred survive.</p>
      </Section>

      <Section id="disputes" title="12. Governing law and disputes">
        <p>These Terms are governed by the laws of the State of New York, without regard to conflict-of-law rules. Any dispute with Art Core will be resolved by binding individual arbitration under the rules of the American Arbitration Association, except that either party may bring qualifying claims in small-claims court. <strong className="text-white">You waive any right to a jury trial or to participate in a class action.</strong> You may opt out of arbitration by emailing {CONTACT} within 30 days of first accepting these Terms.</p>
      </Section>

      <Section id="changes" title="13. Changes and contact">
        <p>We may update these Terms; material changes are announced on the Platform and take effect 14 days after posting (immediately for new users). Continued use means acceptance. Questions: {CONTACT}.</p>
      </Section>
    </>
  );
}

function Privacy() {
  return (
    <>
      <p className="text-sm text-zinc-400">This Privacy Policy explains what Art Core collects, why, and your choices.</p>
      <Section id="collect" title="1. What we collect">
        <p><strong className="text-white">Account:</strong> name, email, password (hashed), role, language, profile bio and images, two-factor settings and trusted devices.</p>
        <p><strong className="text-white">Transactions:</strong> orders, bids, offers, commissions, tickets, payout records, tracking numbers, dispute submissions. Card details are collected and stored by Stripe, never by us. Sellers' identity and bank details are collected by Stripe Connect.</p>
        <p><strong className="text-white">Content and activity:</strong> artworks, posts, comments, messages, likes, saves, follows, reports, studio visits and artwork views (for analytics shown to the artist).</p>
        <p><strong className="text-white">Location:</strong> only when you use "Near me" for events or Upcycle pickup, and only in your browser unless you save it to a listing or event.</p>
        <p><strong className="text-white">Technical:</strong> IP address (used for rate limiting and fraud prevention), browser type, device tokens for trusted devices, push-notification subscriptions you opt into.</p>
      </Section>
      <Section id="use" title="2. How we use it">
        <p>To run the marketplace (checkout, escrow, payouts, delivery confirmation, disputes), send transactional email and push notifications (receipts, tickets, "did your order arrive?", 2FA codes), personalise feeds and event recommendations, show artists analytics about their own studio, prevent fraud and abuse, comply with law, and improve the Platform. We do not sell your personal data.</p>
      </Section>
      <Section id="share" title="3. Who we share it with">
        <p><strong className="text-white">Other users:</strong> your public profile and content; buyers and sellers see each other's names and the shipping details necessary to fulfil an order. <strong className="text-white">Processors:</strong> Stripe (payments, payouts, subscriptions), Resend (email), EasyPost (carrier tracking, when enabled), our hosting and object-storage providers, and AI providers that power optional studio-design suggestions (prompts only, no payment data). <strong className="text-white">Legal:</strong> law enforcement or regulators when required or when necessary to investigate prohibited shipments, fraud, or safety issues.</p>
      </Section>
      <Section id="cookies" title="4. Cookies and local storage">
        <p>We use local storage for your session token, language, and trusted-device token, and a service worker for offline/PWA support and push. We do not run third-party advertising trackers.</p>
      </Section>
      <Section id="retention" title="5. Retention and security">
        <p>We keep transaction records as long as needed for tax, dispute, and legal purposes (typically 7 years). Other data is kept while your account is active and deleted or anonymised within 90 days of account closure, except where retention is required by law. Passwords are bcrypt-hashed; two-factor secrets are stored encrypted-at-rest by our database provider; all traffic is TLS.</p>
      </Section>
      <Section id="rights" title="6. Your rights">
        <p>You can edit your profile, export your saved data, manage notification preferences, revoke trusted devices, and close your account from settings. Depending on where you live (including the EU/UK under GDPR and California under CCPA/CPRA) you may have rights to access, correct, delete, port, or restrict processing of your data and to object to certain uses. Email {CONTACT}; we respond within 30 days. We do not knowingly collect data from anyone under 13, and users under 18 may not sell, bid, or host.</p>
      </Section>
      <Section id="intl" title="7. International transfers and changes">
        <p>Data is processed in the United States. If you access the Platform from elsewhere you consent to that transfer. We will notify you of material changes to this policy on the Platform.</p>
      </Section>
    </>
  );
}

function Refunds() {
  return (
    <>
      <p className="text-sm text-zinc-400">How money moves back when something goes wrong.</p>
      <Section id="artwork" title="1. Artwork, Upcycle, auction and offer purchases">
        <p>Because every piece is unique and sold by an independent artist, <strong className="text-white">sales are final once the buyer confirms receipt</strong> (or delivery is deemed confirmed 3 days after the carrier reports delivery). Before that point, buyers are protected as follows:</p>
        <p><strong className="text-white">Not shipped:</strong> if a seller does not enter tracking within 7 days of the sale (or the listing's stated window), the buyer may request a full refund from the order page.</p>
        <p><strong className="text-white">Not received:</strong> when tracking says delivered but the item did not arrive, tap "I did not receive it". The seller's payout is frozen and Art Core reviews carrier data and both parties' evidence. If the package cannot be shown to have reached the buyer's address, the buyer is refunded.</p>
        <p><strong className="text-white">Damaged or not as described:</strong> open a dispute from the order page within 3 days of confirming receipt, with photos. Outcomes are a full refund, a partial refund, or rejection, decided by Art Core in good faith. Return shipping for a full refund is arranged between buyer and seller; Art Core may require the item to be returned with tracking before releasing a refund.</p>
        <p>Refunds go back to the original payment method via Stripe, typically within 5–10 business days. Platform fees are refunded to the seller in proportion to the refund.</p>
      </Section>
      <Section id="commissions" title="2. Commissions">
        <p>Deposits are held in escrow. If the artist declines or fails to start, the deposit is refunded in full. Once work has begun, deposits are non-refundable unless the artist fails to deliver. The balance is charged only when the buyer approves the delivered work; disputes over delivered commissions follow the "not as described" process above.</p>
      </Section>
      <Section id="tickets" title="3. Event tickets">
        <p>Tickets are refunded automatically in full if the host cancels the event. Tickets are otherwise non-refundable, but may be gifted to someone else through the Platform. If an event is rescheduled, your ticket carries over; if you can't attend the new date, contact the host through the event page.</p>
      </Section>
      <Section id="fees" title="4. Listing fees and Art Core Pro">
        <p>Listing fees, where charged, are non-refundable once the artwork is live. Art Core Pro can be cancelled at any time from the Pro page; you keep Pro perks until the end of the current billing period and are not charged again. We do not prorate partial periods, except where required by law.</p>
      </Section>
      <Section id="chargebacks" title="5. Chargebacks">
        <p>Please contact us before disputing a charge with your bank. Buyers who file a chargeback on an order they confirmed as received, or after a rejected dispute, may have their account suspended and any pending orders cancelled. We share tracking, confirmation, and communication records with Stripe and the card network to contest fraudulent chargebacks.</p>
      </Section>
      <Section id="contact" title="6. Contact">
        <p>Refund questions: {CONTACT}. Include your order number.</p>
      </Section>
    </>
  );
}

const DOCS = {
  terms: { title: "Terms of Service", kicker: "Legal", icon: Scale, body: <Terms /> },
  privacy: { title: "Privacy Policy", kicker: "Legal", icon: ShieldCheck, body: <Privacy /> },
  refunds: { title: "Refund & Dispute Policy", kicker: "Legal", icon: RotateCcw, body: <Refunds /> },
};

export default function Legal() {
  const { doc = "terms" } = useParams();
  const d = DOCS[doc] || DOCS.terms;
  const Icon = d.icon;
  useEffect(() => { window.scrollTo(0, 0); }, [doc]);
  return (
    <div data-testid={`legal-page-${doc}`} className="max-w-3xl mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="label-caps text-[#CCFF00] flex items-center gap-2"><Icon size={12} /> {d.kicker}</div>
      <h1 className="font-anton text-5xl md:text-7xl uppercase mt-4 leading-none">{d.title}</h1>
      <div className="text-xs text-zinc-500 mt-3">Effective {EFFECTIVE} · Art Core Studio</div>
      <nav className="flex flex-wrap gap-2 mt-8" data-testid="legal-nav">
        {Object.entries(DOCS).map(([k, v]) => (
          <Link key={k} to={`/legal/${k}`} data-testid={`legal-tab-${k}`}
            className={`label-caps text-xs px-3 py-2 rounded-sm border transition-colors ${k === doc ? "bg-[#CCFF00] text-black border-[#CCFF00]" : "border-white/15 text-zinc-300 hover:border-[#CCFF00]"}`}>{v.title}</Link>
        ))}
      </nav>
      <div className="mt-6 border-t border-white/8 pt-8">{d.body}</div>
      <div className="mt-12 text-xs text-zinc-500 border border-white/8 rounded-sm p-4">
        This document is provided as a starting point and is not legal advice. Have a licensed attorney in your jurisdiction review it before launch.
      </div>
    </div>
  );
}
