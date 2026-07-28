"use client";

import { useEffect, useState } from "react";
import { API_URL, fmtMoney, PortfolioSnapshot } from "../lib/types";

export default function Portfolio() {
  const [data, setData] = useState<PortfolioSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState(1);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/portfolio`);
      if (!res.ok) throw new Error("Could not load portfolio");
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function trade(side: "buy" | "sell") {
    if (!symbol.trim()) return;
    setMsg(null);
    try {
      const res = await fetch(`${API_URL}/api/portfolio/${side}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbol.trim(), qty }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Trade failed");
      setData(result);
      setMsg(`✓ ${side === "buy" ? "Bought" : "Sold"} ${qty} ${symbol.trim().toUpperCase()}`);
    } catch (err) {
      setMsg(`⚠ ${err instanceof Error ? err.message : "Trade failed"}`);
    }
  }

  async function reset() {
    if (!confirm("Reset the paper portfolio back to starting cash? This clears all holdings and trade history.")) return;
    const res = await fetch(`${API_URL}/api/portfolio/reset`, { method: "POST" });
    setData(await res.json());
    setMsg("Portfolio reset.");
  }

  if (loading) return <p style={{ color: "var(--text-dim)" }}>Loading portfolio…</p>;
  if (error) return <div className="error-banner">⚠ {error}</div>;
  if (!data) return null;

  const returnPositive = data.total_return_pct >= 0;

  return (
    <div>
      <div className="portfolio-summary">
        <div className="stat-card">
          <div className="label">Cash</div>
          <div className="value">{fmtMoney(data.cash)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Holdings value</div>
          <div className="value">{fmtMoney(data.total_holdings_value)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Total portfolio value</div>
          <div className="value">{fmtMoney(data.total_portfolio_value)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Total return</div>
          <div className={`value ${returnPositive ? "positive" : "negative"}`}>
            {returnPositive ? "+" : ""}
            {data.total_return_pct}%
          </div>
        </div>
      </div>

      <div className="trade-form">
        <input type="text" placeholder="Symbol e.g. TCS" value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 140 }} />
        <input type="number" min={1} value={qty} onChange={(e) => setQty(parseInt(e.target.value) || 1)} style={{ width: 70 }} />
        <button className="ghost" onClick={() => trade("buy")}>Paper Buy</button>
        <button className="ghost" onClick={() => trade("sell")}>Paper Sell</button>
        <button className="ghost" onClick={load}>Refresh</button>
        <button className="ghost" onClick={reset} style={{ marginLeft: "auto", color: "var(--bear)" }}>Reset Portfolio</button>
      </div>
      {msg && <p style={{ fontSize: 13, color: "var(--text-dim)" }}>{msg}</p>}

      <h3 className="section-title">Holdings</h3>
      {data.holdings.length === 0 ? (
        <p style={{ color: "var(--text-dim)", fontSize: 13 }}>No open positions.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th><th>Qty</th><th>Avg Price</th><th>Current</th><th>Value</th><th>Unrealized P&L</th>
            </tr>
          </thead>
          <tbody>
            {data.holdings.map((h) => (
              <tr key={h.symbol}>
                <td>{h.symbol}</td>
                <td>{h.qty}</td>
                <td>{fmtMoney(h.avg_price)}</td>
                <td>{fmtMoney(h.current_price)}</td>
                <td>{fmtMoney(h.value)}</td>
                <td style={{ color: h.unrealized_pnl >= 0 ? "var(--bull)" : "var(--bear)" }}>
                  {h.unrealized_pnl >= 0 ? "+" : ""}
                  {fmtMoney(h.unrealized_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 className="section-title">Trade History</h3>
      {data.trade_history.length === 0 ? (
        <p style={{ color: "var(--text-dim)", fontSize: 13 }}>No trades yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Type</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Realized P&L</th><th>Time</th></tr>
          </thead>
          <tbody>
            {data.trade_history.map((t, i) => (
              <tr key={i}>
                <td><span className={`badge ${t.type === "BUY" ? "buy" : "sell"}`}>{t.type}</span></td>
                <td>{t.symbol}</td>
                <td>{t.qty}</td>
                <td>{fmtMoney(t.price)}</td>
                <td>
                  {t.realized_pnl !== undefined ? (
                    <span style={{ color: t.realized_pnl >= 0 ? "var(--bull)" : "var(--bear)" }}>
                      {t.realized_pnl >= 0 ? "+" : ""}
                      {fmtMoney(t.realized_pnl)}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td style={{ color: "var(--text-dim)", fontSize: 12 }}>{t.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
