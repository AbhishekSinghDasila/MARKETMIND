export type Status = "idle" | "active" | "done";

export type StepEvent = {
  agent: string;
  type: "start" | "result" | "final" | "error";
  message: string;
  data?: unknown;
};

export type NewsItem = {
  source: string;
  title: string;
  summary: string;
  link: string;
  published: string;
  sector?: string;
  sentiment?: "bullish" | "bearish" | "neutral";
  reason?: string;
};

export type SectorStock = { ticker: string; last_price: number; change_5d_pct: number };

export type SectorMomentum = {
  sector: string;
  avg_change_5d_pct: number;
  avg_change_1m_pct: number;
  stocks: SectorStock[];
};

export type SectorOutlook = {
  sector: string;
  outlook: "bullish" | "bearish" | "neutral";
  confidence: "low" | "medium" | "high";
  reasoning: string;
  momentum: SectorMomentum;
  news_used: NewsItem[];
};

export type PriceLevel = { price: number; touches: number };

export type PricePoint = { date: string; close: number };

export type TechnicalSnapshot = {
  symbol: string;
  current_price: number;
  trend: string;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  rsi_14: number | null;
  macd_line: number | null;
  macd_signal: number | null;
  macd_bias: "bullish" | "bearish";
  resistance_levels: PriceLevel[];
  support_levels: PriceLevel[];
  narrative?: string;
  price_history: PricePoint[];
};

export type IndexView = {
  overall_view: "bullish" | "bearish" | "neutral";
  reasoning: string;
  nifty: TechnicalSnapshot;
  sensex: TechnicalSnapshot;
};

export type HorizonCall = {
  bias: "buy" | "sell" | "hold";
  confidence: "low" | "medium" | "high";
  entry: number | null;
  target: number | null;
  stop_loss: number | null;
  reasoning: string;
};

export type RiskData = {
  symbol: string;
  atr_14: number | null;
  volatility_pct: number | null;
  risk_label: "low" | "medium" | "high" | "unknown";
  suggested_position_qty: number | null;
  reference_capital: number;
  risk_pct_per_trade: number;
  current_price: number;
  risk_summary: string;
};

export type Decision = {
  intraday: HorizonCall;
  swing: HorizonCall;
  long_term: HorizonCall;
  overall_summary: string;
};

export type Holding = {
  symbol: string;
  qty: number;
  avg_price: number;
  current_price: number;
  value: number;
  unrealized_pnl: number;
};

export type Trade = {
  type: "BUY" | "SELL";
  symbol: string;
  qty: number;
  price: number;
  realized_pnl?: number;
  timestamp: string;
};

export type PortfolioSnapshot = {
  cash: number;
  holdings: Holding[];
  total_holdings_value: number;
  total_portfolio_value: number;
  starting_cash: number;
  total_return_pct: number;
  realized_pnl: number;
  trade_history: Trade[];
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Shared SSE-stream reader used by both the Market Overview and Stock
// Analysis tabs — reads a fetch() POST response body as Server-Sent Events.
export async function streamEvents(
  path: string,
  body: object,
  onEvent: (evt: StepEvent) => void
): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.body) throw new Error("No response stream from server");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const jsonStr = line.slice(5).trim();
      if (!jsonStr) continue;
      onEvent(JSON.parse(jsonStr));
    }
  }
}

export function fmtMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
