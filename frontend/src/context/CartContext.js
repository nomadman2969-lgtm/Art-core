import React, { createContext, useContext, useEffect, useState } from "react";

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [items, setItems] = useState(() => {
    try { return JSON.parse(localStorage.getItem("hom_cart") || "[]"); } catch { return []; }
  });
  useEffect(() => { localStorage.setItem("hom_cart", JSON.stringify(items)); }, [items]);

  const add = (artwork) => {
    if (!Number.isFinite(Number(artwork?.price))) return;
    setItems((prev) => prev.find((i) => i.id === artwork.id) ? prev : [...prev, { id: artwork.id, title: artwork.title, price: artwork.price, image: artwork.images?.[0], artist: artwork.artist?.name }]);
  };
  const remove = (id) => setItems((prev) => prev.filter((i) => i.id !== id));
  const clear = () => setItems([]);
  const total = items.reduce((s, i) => s + (Number.isFinite(Number(i.price)) ? Number(i.price) : 0), 0);

  return <CartContext.Provider value={{ items, add, remove, clear, total }}>{children}</CartContext.Provider>;
}
export const useCart = () => useContext(CartContext);
