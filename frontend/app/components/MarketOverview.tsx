"use client";

import { useState } from "react";
import { streamEvents, StepEvent, SectorOutlook, IndexView, Status } from "../lib/types";

const SECTORS: { key: string; label: string }[] = [
  { key: "BANKING", label: "Banking" },
  { key: "IT", label: "IT" },
  { key: "FMCG", label: "FMCG" },
  { key: "OIL_GAS", label: "Oil & Gas" },
  { key: "PHARMA", label: "Pharma" },
];

type OverviewState = {
  news: { status: Status; count: number };
  sectors: Record<string, { status: Status; outlook?: SectorOutlook }>;
  index: { status: Status; data?: IndexView };
};

function initialState(): OverviewState {
  const sectors: OverviewState["sectors"] = {};
  for (const s of SECTORS) sectors[s.key] = { status: "idle" };
  return { news: { status: "idle", count: 0 }, sectors, index: { status: "idle" } };
}

function applyEvent(prev: OverviewState, evt: StepEvent): OverviewState {
  const next: OverviewState = {
    news: { ...prev.news },
    sectors: { ...prev.sectors },
    index: { ...prev.index },
  };
  if (evt.agent === "News" && evt.type === "start") {
    next.news.status = "active";
  } else if (evt.agent === "News" && evt.type === "result") {
    next.news.status = "done";
    next.news.count = Array.isArray(evt.data) ? evt.data.length : 0;
  } else if (evt.agent.startsWith("Sector:")) {
    const key = evt.agent.split(":")[1];
    if (evt.type === "start") {
      next.sectors[key] = { status: "active" };
    } else if (evt.type === "result") {
      next.sectors[key] = { status: "done", outlook: evt.data as SectorOutlook };
    }
  } else if (evt.agent === "Index" && evt.type === "start") {
    next.index.status = "active";
  } else if (evt.agent === "Index" && evt.type === "result") {
    next.index.status = "done";
    next.index.data = evt.data as IndexView;
  }
  return next;
}

export default function MarketOverview() {
  const [state, setState] = useState<OverviewState>(initialState());
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ran, setRan] = useState(false);

  async function runScan() {
    setState(initialState());
    setError(null);
    setRunning(true);
    setRan(true);
    try {
      await streamEvents("/api/market-overview", {}, (evt) => {
        if (evt.type === "error") setError(evt.message);
        else setState((prev) => applyEvent(prev, evt));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="goal-form">
        <span style={{ color: "var(--text-dim)", fontSize: 14 }}>
          Scans live news + 5 sectors + Nifty/Sensex
        </span>
        <button className="run" onClick={runScan} disabled={running} style={{ marginLeft: "auto" }}>
          {running ? "Scanning…" : ran ? "Re-run scan →" : "Run market scan →"}
        </button>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {ran && (
        <>
          <div className="sector-grid">
            {SECTORS.map(({ key, label }) => {
              const s = state.sectors[key];
              return (
                <div
                  key={key}
                  className={`sector-card ${s.status === "idle" ? "loading" : ""} ${
                    s.outlook ? (s.outlook.outlook === "neutral" ? "neutral-tone" : s.outlook.outlook) : ""
                  }`}
                >
                  <span className="sector-name">{label}</span>
                  {!s.outlook ? (
                    <span className="placeholder" style={{ fontSize: 12, color: "var(--text-dim)" }}>
                      {s.status === "active" ? "Analyzing…" : "Waiting…"}
                    </span>
                  ) : (
                    <>
                      <span className={`badge ${s.outlook.outlook}`}>{s.outlook.outlook}</span>
                      <span className="sector-momentum">
                        5D {s.outlook.momentum.avg_change_5d_pct > 0 ? "+" : ""}
                        {s.outlook.momentum.avg_change_5d_pct}% · 1M{" "}
                        {s.outlook.momentum.avg_change_1m_pct > 0 ? "+" : ""}
                        {s.outlook.momentum.avg_change_1m_pct}%
                      </span>
                      <span className="sector-reasoning">{s.outlook.reasoning}</span>
                    </>
                  )}
                </div>
              );
            })}
          </div>

          <div className="index-card">
            <h3>Nifty / Sensex — Overall Market View</h3>
            {!state.index.data ? (
              <span className="placeholder" style={{ color: "var(--text-dim)", fontSize: 13 }}>
                {state.index.status === "active" ? "Synthesizing overall view…" : "Waiting on sector agents…"}
              </span>
            ) : (
              <>
                <span className={`badge ${state.index.data.overall_view}`}>{state.index.data.overall_view}</span>
                <div className="index-stats">
                  <span>
                    Nifty 50: <b>{state.index.data.nifty.current_price}</b> ({state.index.data.nifty.trend})
                  </span>
                  <span>
                    Sensex: <b>{state.index.data.sensex.current_price}</b> ({state.index.data.sensex.trend})
                  </span>
                </div>
                <p style={{ fontSize: 13.5, color: "var(--text-dim)", lineHeight: 1.6 }}>
                  {state.index.data.reasoning}
                </p>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
