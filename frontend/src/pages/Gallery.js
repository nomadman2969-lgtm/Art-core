import { useTranslation } from "react-i18next";
import React, { useEffect, useState } from "react";
import { api } from "../api";
import { ArtCard } from "../components/ArtCard";

export default function Marketplace() {
  const { t } = useTranslation();
  const [artworks, setArtworks] = useState([]);
  const [medium, setMedium] = useState(new URLSearchParams(window.location.search).get("medium") || "");
  const [sort, setSort] = useState("recent");
  const [maxPrice, setMaxPrice] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (medium) params.append("medium", medium);
    if (maxPrice) params.append("max_price", maxPrice);
    params.append("sort", sort);
    api.get(`/artworks?${params.toString()}`).then((r) => setArtworks(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, [medium, sort, maxPrice]);

  return (
    <div data-testid="marketplace-page" className="max-w-[1600px] mx-auto px-6 md:px-12 pt-16 pb-32">
      <div className="mb-12">
        <div className="label-caps text-[#CCFF00]">{t("market.kicker")}</div>
        <h1 className="font-anton text-6xl md:text-9xl uppercase mt-4 leading-[0.85]">{t("market.title")}</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-y border-white/8 py-6 mb-12">
        <select data-testid="filter-medium" value={medium} onChange={(e) => setMedium(e.target.value)}
          className="bg-transparent border border-white/12 px-4 py-2 label-caps text-xs rounded-sm">
          <option value="">{t("market.all_mediums")}</option>
          {["Oil", "Acrylic", "Watercolor", "Mixed Media", "Digital", "Photography"].map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select data-testid="filter-sort" value={sort} onChange={(e) => setSort(e.target.value)}
          className="bg-transparent border border-white/12 px-4 py-2 label-caps text-xs rounded-sm">
          <option value="recent">{t("market.newest")}</option>
          <option value="price_asc">{t("market.price_low")}</option>
          <option value="price_desc">{t("market.price_high")}</option>
        </select>
        <input data-testid="filter-max-price" type="number" placeholder={t("market.max_price")} value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          className="bg-transparent border border-white/12 px-4 py-2 label-caps text-xs w-40 rounded-sm" />
        <div className="ml-auto label-caps text-zinc-500">{t("market.works", { count: artworks.length })}</div>
      </div>

      {loading ? (
        <div className="text-zinc-500 py-24 text-center label-caps">Loading...</div>
      ) : artworks.length === 0 ? (
        <div className="text-zinc-500 py-24 text-center label-caps border border-dashed border-white/10 rounded-sm">No pieces match your filter.</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {artworks.map((a, i) => <ArtCard key={a.id} art={a} tall={i % 6 === 0} />)}
        </div>
      )}
    </div>
  );
}
