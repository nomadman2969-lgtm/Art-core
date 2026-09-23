import React from "react";
import { Link } from "react-router-dom";
import { Palette, Package, MessageCircle, Ticket, Bookmark, Sparkles, Compass, Truck } from "lucide-react";

const ICONS = { palette: Palette, package: Package, message: MessageCircle, ticket: Ticket, bookmark: Bookmark, sparkles: Sparkles, compass: Compass, truck: Truck };

export function EmptyState({ icon = "sparkles", title, body, cta, to, onClick, secondary, secondaryTo, testId = "empty-state" }) {
  const Icon = ICONS[icon] || Sparkles;
  return (
    <div data-testid={testId} className="border border-dashed border-white/10 rounded-sm py-16 px-6 text-center max-w-xl mx-auto">
      <div className="w-12 h-12 rounded-full bg-[#CCFF00]/10 text-[#CCFF00] flex items-center justify-center mx-auto"><Icon size={22} /></div>
      <div className="font-anton text-2xl md:text-3xl uppercase mt-5">{title}</div>
      {body && <p className="text-sm text-zinc-400 mt-3 leading-relaxed">{body}</p>}
      <div className="flex flex-wrap justify-center gap-3 mt-6">
        {cta && (to ? <Link to={to} className="btn-lime" data-testid={`${testId}-cta`}>{cta}</Link> : <button onClick={onClick} className="btn-lime" data-testid={`${testId}-cta`}>{cta}</button>)}
        {secondary && secondaryTo && <Link to={secondaryTo} className="btn-ghost" data-testid={`${testId}-secondary`}>{secondary}</Link>}
      </div>
    </div>
  );
}
