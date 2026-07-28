"use client";

import { useEffect, useState } from "react";
import { API_URL } from "../lib/types";

type Quote = { price: number; change_pct: number } | null;
type Quotes = Record<string, Quote>;

export default function TickerTape() {
  const [quotes, setQuotes] = useState<Quotes | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/ticker`)
      .then((r) => r.json())
      .then(setQuotes)
      .catch(() => setQuotes(null));
  }, []);

  const items = quotes
    ? Object.entries(quotes)
        .filter(([, q]) => q !== null)
        .map(([name, q]) => (
          <span className="ticker-item" key={name}>
            {name} <b>{q!.price.toLocaleString("en-IN")}</b>
            <span className={q!.change_pct >= 0 ? "up" : "down"}>
              {q!.change_pct >= 0 ? "▲" : "▼"} {Math.abs(q!.change_pct)}%
            </span>
          </span>
        ))
    : [<span className="ticker-item" key="loading">Loading live indices…</span>];

  // Duplicate the list so the CSS marquee loop (translateX -50%) is seamless.
  return (
    <div className="ticker-tape">
      <div className="ticker-track">
        {items}
        {items}
      </div>
    </div>
  );
}
