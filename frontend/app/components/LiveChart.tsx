"use client";

import { useEffect, useRef, useState } from "react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { API_URL } from "../lib/types";

type LivePoint = { time: string; close: number };
type LiveData = { symbol: string; points: LivePoint[]; last_price: number; change_pct: number };

const POLL_MS = 30000;

export default function LiveChart({ symbol }: { symbol: string }) {
  const [data, setData] = useState<LiveData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchOnce() {
    try {
      const res = await fetch(`${API_URL}/api/live/${encodeURIComponent(symbol)}`);
      if (!res.ok) throw new Error("Live data unavailable for this symbol right now");
      setData(await res.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Live data unavailable");
    }
  }

  useEffect(() => {
    fetchOnce();
    intervalRef.current = setInterval(fetchOnce, POLL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  if (error) return <div className="live-chart-error">{error}</div>;
  if (!data) return <div className="live-chart-loading">Loading live chart…</div>;

  const up = data.change_pct >= 0;

  return (
    <div className="live-chart-card">
      <div className="live-chart-head">
        <span className="live-dot" />
        <span className="live-label">LIVE · {data.symbol}</span>
        <span className="live-price">
          ₹{data.last_price.toLocaleString("en-IN")}{" "}
          <span className={up ? "up" : "down"}>
            {up ? "▲" : "▼"} {Math.abs(data.change_pct)}%
          </span>
        </span>
        <span className="live-refresh">updates every 30s</span>
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data.points} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="liveGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={up ? "#16c784" : "#ea3943"} stopOpacity={0.35} />
              <stop offset="100%" stopColor={up ? "#16c784" : "#ea3943"} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#23262e" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "#8b93a3", fontSize: 10 }} minTickGap={30} />
          <YAxis domain={["auto", "auto"]} tick={{ fill: "#8b93a3", fontSize: 10 }} width={50} />
          <Tooltip contentStyle={{ background: "#15181f", border: "1px solid #23262e", borderRadius: 6, fontSize: 12 }} />
          <Area type="monotone" dataKey="close" stroke={up ? "#16c784" : "#ea3943"} strokeWidth={2} fill="url(#liveGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
