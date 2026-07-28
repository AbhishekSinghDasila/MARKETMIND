"use client";

import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, ReferenceLine, Tooltip, CartesianGrid,
} from "recharts";
import { TechnicalSnapshot } from "../lib/types";

export default function PriceChart({ snapshot }: { snapshot: TechnicalSnapshot }) {
  const data = snapshot.price_history;
  if (!data || data.length === 0) return null;

  const prices = data.map((d) => d.close);
  const allLevels = [
    ...snapshot.support_levels.map((l) => l.price),
    ...snapshot.resistance_levels.map((l) => l.price),
    ...prices,
  ];
  const min = Math.min(...allLevels) * 0.98;
  const max = Math.max(...allLevels) * 1.02;

  return (
    <div className="chart-container">
      <div className="chart-legend">
        <span className="leg-price">Close price</span>
        <span className="leg-support">Support</span>
        <span className="leg-resistance">Resistance</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid stroke="#23262e" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#8b93a3", fontSize: 10 }}
            tickFormatter={(d: string) => d.slice(5)}
            minTickGap={40}
          />
          <YAxis domain={[min, max]} tick={{ fill: "#8b93a3", fontSize: 10 }} width={55} />
          <Tooltip
            contentStyle={{ background: "#15181f", border: "1px solid #23262e", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#8b93a3" }}
          />
          {snapshot.support_levels.map((l, i) => (
            <ReferenceLine key={`s${i}`} y={l.price} stroke="#16c784" strokeDasharray="4 4" strokeWidth={1.5} />
          ))}
          {snapshot.resistance_levels.map((l, i) => (
            <ReferenceLine key={`r${i}`} y={l.price} stroke="#ea3943" strokeDasharray="4 4" strokeWidth={1.5} />
          ))}
          <Line type="monotone" dataKey="close" stroke="#f0b90b" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
