"use client";

import { useState } from "react";
import PriceChart from "./PriceChart";
import LiveChart from "./LiveChart";
import {
  streamEvents, StepEvent, SectorOutlook, IndexView, TechnicalSnapshot, RiskData, Decision,
  HorizonCall, Status, API_URL, fmtMoney,
} from "../lib/types";

const QUICK_SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "SUNPHARMA", "^NSEI"];

type AnalysisState = {
  symbol: string;
  news: { status: Status; count: number };
  sector: { status: Status; outlook?: SectorOutlook | null; skipped?: boolean; message?: string };
  index: { status: Status; data?: IndexView };
  technical: { status: Status; data?: TechnicalSnapshot };
  risk: { status: Status; data?: RiskData };
  decision: { status: Status; data?: Decision };
};

function initialState(): AnalysisState {
  return {
    symbol: "",
    news: { status: "idle", count: 0 },
    sector: { status: "idle" },
    index: { status: "idle" },
    technical: { status: "idle" },
    risk: { status: "idle" },
    decision: { status: "idle" },
  };
}

function applyEvent(prev: AnalysisState, evt: StepEvent): AnalysisState {
  const next: AnalysisState = { ...prev };
  if (evt.agent === "News") {
    if (evt.type === "start") next.news = { ...next.news, status: "active" };
    else if (evt.type === "result")
      next.news = { status: "done", count: Array.isArray(evt.data) ? evt.data.length : 0 };
  } else if (evt.agent.startsWith("Sector")) {
    if (evt.type === "start") next.sector = { status: "active" };
    else if (evt.type === "result") {
      if (evt.data) next.sector = { status: "done", outlook: evt.data as SectorOutlook };
      else next.sector = { status: "done", skipped: true, message: evt.message };
    }
  } else if (evt.agent === "Index") {
    if (evt.type === "start") next.index = { ...next.index, status: "active" };
    else if (evt.type === "result") next.index = { status: "done", data: evt.data as IndexView };
  } else if (evt.agent === "Technical") {
    if (evt.type === "start") next.technical = { ...next.technical, status: "active" };
    else if (evt.type === "result") next.technical = { status: "done", data: evt.data as TechnicalSnapshot };
  } else if (evt.agent === "Risk") {
    if (evt.type === "start") next.risk = { ...next.risk, status: "active" };
    else if (evt.type === "result") next.risk = { status: "done", data: evt.data as RiskData };
  } else if (evt.agent === "Decision") {
    if (evt.type === "start") next.decision = { ...next.decision, status: "active" };
    else if (evt.type === "result") next.decision = { status: "done", data: evt.data as Decision };
  }
  return next;
}

function StatusBadge({ status, activeLabel, doneLabel }: { status: Status; activeLabel: string; doneLabel: string }) {
  if (status === "idle") return <span className="node-status">Waiting</span>;
  if (status === "active") return <span className="node-status active">{activeLabel}</span>;
  return <span className="node-status">{doneLabel}</span>;
}

function HorizonCard({ title, call }: { title: string; call: HorizonCall }) {
  return (
    <div className={`horizon-card ${call.bias}`}>
      <div className="horizon-title">{title}</div>
      <span className={`badge ${call.bias}`}>{call.bias}</span>{" "}
      <span className="badge hold" style={{ opacity: 0.75 }}>{call.confidence} confidence</span>
      <div className="horizon-row"><span>Entry</span><b>{fmtMoney(call.entry)}</b></div>
      <div className="horizon-row"><span>Target</span><b>{fmtMoney(call.target)}</b></div>
      <div className="horizon-row"><span>Stop-loss</span><b>{fmtMoney(call.stop_loss)}</b></div>
      <div className="horizon-reasoning">{call.reasoning}</div>
    </div>
  );
}

export default function StockAnalysis() {
  const [symbolInput, setSymbolInput] = useState("");
  const [state, setState] = useState<AnalysisState>(initialState());
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ran, setRan] = useState(false);
  const [tradeQty, setTradeQty] = useState(1);
  const [tradeMsg, setTradeMsg] = useState<string | null>(null);

  async function runAnalysis(symbolOverride?: string) {
    const sym = (symbolOverride ?? symbolInput).trim();
    if (!sym || running) return;
    setSymbolInput(sym);
    setState({ ...initialState(), symbol: sym.toUpperCase() });
    setError(null);
    setTradeMsg(null);
    setRunning(true);
    setRan(true);
    try {
      await streamEvents("/api/analyze", { symbol: sym }, (evt) => {
        if (evt.type === "error") setError(evt.message);
        else setState((prev) => applyEvent(prev, evt));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setRunning(false);
    }
  }

  async function paperTrade(side: "buy" | "sell") {
    setTradeMsg(null);
    try {
      const res = await fetch(`${API_URL}/api/portfolio/${side}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: state.symbol, qty: tradeQty }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Trade failed");
      setTradeMsg(`✓ Paper ${side} of ${tradeQty} ${state.symbol} recorded. Check the Paper Portfolio tab.`);
    } catch (err) {
      setTradeMsg(`⚠ ${err instanceof Error ? err.message : "Trade failed"}`);
    }
  }

  return (
    <div>
      <form
        className="goal-form"
        onSubmit={(e) => {
          e.preventDefault();
          runAnalysis();
        }}
      >
        <input
          type="text"
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          placeholder="e.g. RELIANCE, TCS, HDFCBANK, ^NSEI"
        />
        <button className="run" type="submit" disabled={running}>
          {running ? "Analyzing…" : "Analyze →"}
        </button>
      </form>

      <div className="quick-symbols">
        {QUICK_SYMBOLS.map((s) => (
          <button key={s} className="chip-btn" disabled={running} onClick={() => runAnalysis(s)}>
            {s}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {ran && state.symbol && <LiveChart symbol={state.symbol} />}

      {ran && (
        <div className="pipeline">
          {/* News */}
          <div className="pipeline-node">
            <div className="node-rail">
              <div className={`node-dot ${state.news.status === "active" ? "active" : ""}`}>1</div>
              <div className={`node-line ${state.news.status === "done" ? "filled" : ""}`} />
            </div>
            <div className="node-card">
              <div className="node-head">
                <span className="node-title">NEWS</span>
                <StatusBadge status={state.news.status} activeLabel="Fetching…" doneLabel={`${state.news.count} articles tagged`} />
              </div>
              <div className="node-body">
                {state.news.status === "idle" && <span className="placeholder">Will fetch and tag today's financial news</span>}
              </div>
            </div>
          </div>

          {/* Sector */}
          <div className="pipeline-node">
            <div className="node-rail">
              <div className={`node-dot ${state.sector.status === "active" ? "active" : ""}`}>2</div>
              <div className={`node-line ${state.sector.status === "done" ? "filled" : ""}`} />
            </div>
            <div className="node-card">
              <div className="node-head">
                <span className="node-title">SECTOR</span>
                <StatusBadge status={state.sector.status} activeLabel="Analyzing…" doneLabel={state.sector.skipped ? "Not classified" : "Done"} />
              </div>
              <div className="node-body">
                {state.sector.status === "idle" && <span className="placeholder">Will analyze this stock's sector</span>}
                {state.sector.skipped && <span>{state.sector.message}</span>}
                {state.sector.outlook && (
                  <>
                    <span className={`badge ${state.sector.outlook.outlook}`}>{state.sector.outlook.outlook}</span>
                    <p style={{ marginTop: 6 }}>{state.sector.outlook.reasoning}</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Index */}
          <div className="pipeline-node">
            <div className="node-rail">
              <div className={`node-dot ${state.index.status === "active" ? "active" : ""}`}>3</div>
              <div className={`node-line ${state.index.status === "done" ? "filled" : ""}`} />
            </div>
            <div className="node-card">
              <div className="node-head">
                <span className="node-title">INDEX (NIFTY/SENSEX)</span>
                <StatusBadge status={state.index.status} activeLabel="Synthesizing…" doneLabel="Done" />
              </div>
              <div className="node-body">
                {state.index.status === "idle" && <span className="placeholder">Will assess the overall market view</span>}
                {state.index.data && (
                  <>
                    <span className={`badge ${state.index.data.overall_view}`}>{state.index.data.overall_view}</span>
                    <p style={{ marginTop: 6 }}>{state.index.data.reasoning}</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Technical */}
          <div className="pipeline-node">
            <div className="node-rail">
              <div className={`node-dot ${state.technical.status === "active" ? "active" : ""}`}>4</div>
              <div className={`node-line ${state.technical.status === "done" ? "filled" : ""}`} />
            </div>
            <div className="node-card">
              <div className="node-head">
                <span className="node-title">TECHNICAL</span>
                <StatusBadge status={state.technical.status} activeLabel="Computing…" doneLabel="Done" />
              </div>
              <div className="node-body">
                {state.technical.status === "idle" && <span className="placeholder">Will compute support/resistance, RSI, MACD from real price data</span>}
                {state.technical.data && (
                  <>
                    <p>
                      Price <b style={{ color: "var(--text)" }}>{fmtMoney(state.technical.data.current_price)}</b> · Trend: {state.technical.data.trend} · RSI(14): {state.technical.data.rsi_14 ?? "—"} · MACD: {state.technical.data.macd_bias}
                    </p>
                    <PriceChart snapshot={state.technical.data} />
                    <div className="level-list">
                      {state.technical.data.support_levels.map((l, i) => (
                        <span className="level-chip support-chip" key={`s${i}`}>Support {fmtMoney(l.price)} ({l.touches}x)</span>
                      ))}
                      {state.technical.data.resistance_levels.map((l, i) => (
                        <span className="level-chip resistance-chip" key={`r${i}`}>Resistance {fmtMoney(l.price)} ({l.touches}x)</span>
                      ))}
                    </div>
                    {state.technical.data.narrative && <p style={{ marginTop: 8 }}>{state.technical.data.narrative}</p>}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Risk */}
          <div className="pipeline-node">
            <div className="node-rail">
              <div className={`node-dot ${state.risk.status === "active" ? "active" : ""}`}>5</div>
              <div className={`node-line ${state.risk.status === "done" ? "filled" : ""}`} />
            </div>
            <div className="node-card">
              <div className="node-head">
                <span className="node-title">RISK</span>
                <StatusBadge
                  status={state.risk.status}
                  activeLabel="Assessing…"
                  doneLabel={state.risk.data ? `${state.risk.data.risk_label} volatility` : "Done"}
                />
              </div>
              <div className="node-body">
                {state.risk.status === "idle" && <span className="placeholder">Will assess volatility and suggest a position size</span>}
                {state.risk.data && (
                  <>
                    <div className="level-list">
                      <span className="level-chip">ATR(14) {state.risk.data.atr_14 ?? "—"}</span>
                      <span className="level-chip">Volatility {state.risk.data.volatility_pct ?? "—"}%</span>
                      <span className="level-chip">
                        Suggested size: {state.risk.data.suggested_position_qty ?? "—"} shares
                        (₹{state.risk.data.reference_capital.toLocaleString("en-IN")} @ {state.risk.data.risk_pct_per_trade}% risk)
                      </span>
                    </div>
                    <p style={{ marginTop: 8 }}>{state.risk.data.risk_summary}</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Decision */}
          <div className="pipeline-node">
            <div className="node-rail">
              <div className={`node-dot ${state.decision.status === "active" ? "active" : ""}`}>6</div>
            </div>
            <div className="node-card">
              <div className="node-head">
                <span className="node-title">DECISION</span>
                <StatusBadge status={state.decision.status} activeLabel="Deciding…" doneLabel="Done" />
              </div>
              <div className="node-body">
                {state.decision.status === "idle" && <span className="placeholder">Will combine everything into intraday / swing / long-term calls</span>}
                {state.decision.data && (
                  <>
                    <p>{state.decision.data.overall_summary}</p>
                    <div className="horizon-grid">
                      <HorizonCard title="Intraday" call={state.decision.data.intraday} />
                      <HorizonCard title="Swing" call={state.decision.data.swing} />
                      <HorizonCard title="Long-term" call={state.decision.data.long_term} />
                    </div>

                    <div className="trade-form">
                      <span style={{ fontSize: 13, color: "var(--text-dim)" }}>Paper trade {state.symbol}:</span>
                      <input
                        type="number"
                        min={1}
                        value={tradeQty}
                        onChange={(e) => setTradeQty(parseInt(e.target.value) || 1)}
                        style={{ width: 70 }}
                      />
                      <button className="ghost" onClick={() => paperTrade("buy")}>Paper Buy</button>
                      <button className="ghost" onClick={() => paperTrade("sell")}>Paper Sell</button>
                    </div>
                    {tradeMsg && <p style={{ fontSize: 13 }}>{tradeMsg}</p>}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
