"use client";

import { useState } from "react";
import TickerTape from "./components/TickerTape";
import MarketOverview from "./components/MarketOverview";
import StockAnalysis from "./components/StockAnalysis";
import Portfolio from "./components/Portfolio";

type Tab = "overview" | "analyze" | "portfolio";

const TAB_META: Record<Tab, { label: string; desc: string }> = {
  overview: { label: "Market Overview", desc: "News + 5 sector agents + Nifty/Sensex index agent" },
  analyze: { label: "Analyze Stock", desc: "Full pipeline: News → Sector → Index → Technical → Decision" },
  portfolio: { label: "Paper Portfolio", desc: "Simulated holdings, P&L, and trade history — virtual money only" },
};

function LogoMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="10" width="3" height="8" fill="#f0b90b" />
      <rect x="8.5" y="5" width="3" height="13" fill="#f0b90b" />
      <rect x="15" y="1" width="3" height="17" fill="#f0b90b" />
    </svg>
  );
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="app-shell">
      <nav className="topnav">
        <div className="brand">
          <LogoMark />
          <span className="brand-name">MARKETMIND</span>
        </div>
        <div className="nav-tabs">
          {(Object.keys(TAB_META) as Tab[]).map((t) => (
            <button key={t} className={`nav-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
              {TAB_META[t].label}
            </button>
          ))}
        </div>
      </nav>

      <TickerTape />

      <div className="dashboard">
        <div className="page-head">
          <div>
            <h2 className="page-title">{TAB_META[tab].label}</h2>
            <p className="page-desc">{TAB_META[tab].desc}</p>
          </div>
        </div>

        {tab === "overview" && <MarketOverview />}
        {tab === "analyze" && <StockAnalysis />}
        {tab === "portfolio" && <Portfolio />}
      </div>

      <footer className="app-footer">
        <p style={{ marginBottom: 8 }}>FastAPI + Groq backend on Render · Next.js frontend on Vercel</p>
        <p className="disclaimer-footer">
          Educational project — not investment advice. No system can reliably predict market
          movements. All trades here are simulated (&quot;paper trading&quot;) — nothing places a
          real order. Consult a licensed financial advisor before making real investment
          decisions.
        </p>
      </footer>
    </div>
  );
}
