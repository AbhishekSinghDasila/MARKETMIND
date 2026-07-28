import json
from unittest.mock import patch, MagicMock

import agents

FAKE_NEWS = [
    {"source": "ET", "title": "RBI holds repo rate steady", "summary": "...", "link": "", "published": ""},
    {"source": "MC", "title": "IT firms see strong Q3 hiring", "summary": "...", "link": "", "published": ""},
    {"source": "LM", "title": "Oil prices dip on supply glut", "summary": "...", "link": "", "published": ""},
]

FAKE_MOMENTUM = {
    "sector": "IT", "avg_change_5d_pct": 1.2, "avg_change_1m_pct": 3.4,
    "stocks": [{"ticker": "TCS.NS", "last_price": 3800.0, "change_5d_pct": 1.1}],
}

FAKE_TECHNICAL = {
    "symbol": "TCS.NS", "current_price": 3800.0, "trend": "uptrend",
    "sma20": 3750.0, "sma50": 3700.0, "sma200": 3600.0, "rsi_14": 58.0,
    "macd_line": 5.0, "macd_signal": 3.0, "macd_bias": "bullish",
    "resistance_levels": [{"price": 3850.0, "touches": 2}],
    "support_levels": [{"price": 3700.0, "touches": 3}],
    "price_history": [{"date": "2026-07-01", "close": 3780.0}, {"date": "2026-07-02", "close": 3800.0}],
    "atr_14": 45.2, "volatility_pct": 1.19, "risk_label": "low",
    "suggested_position_qty": 14, "reference_capital": 100000, "risk_pct_per_trade": 1.0,
}


def fake_call_llm(client, system, user, json_mode=False, max_tokens=900, temperature=0.4):
    if "News Agent" in system:
        return json.dumps({"tags": [
            {"index": 0, "sector": "MACRO", "sentiment": "neutral", "impact": "medium", "reason": "rate hold"},
            {"index": 1, "sector": "IT", "sentiment": "bullish", "impact": "high", "reason": "hiring up"},
            {"index": 2, "sector": "OIL_GAS", "sentiment": "bearish", "impact": "medium", "reason": "oil dip"},
        ]})
    if "Sector Agent" in system:
        return json.dumps({"outlook": "bullish", "confidence": "medium", "reasoning": "5-day momentum of +1.2% led by hiring news."})
    if "Index Agent" in system:
        return json.dumps({"overall_view": "bullish", "reasoning": "IT sector bullish at +1.2% momentum; indices in uptrend with RSI neutral."})
    if "Technical Agent" in system:
        return json.dumps({"narrative": "Price above rising SMA20/50/200 with RSI at 58 (neutral) and MACD bullish, confirming the uptrend."})
    if "Risk Agent" in system:
        return json.dumps({"risk_summary": "ATR of 45.2 (1.19% of price) marks this as low volatility; suggested size of 14 shares reflects a tight 1% risk stop."})
    if "Decision Agent" in system:
        return json.dumps({
            "intraday": {"bias": "buy", "confidence": "medium", "entry": 3800.0, "target": 3850.0, "stop_loss": 3760.0, "reasoning": "RSI 58 neutral, MACD bullish, near support 3700."},
            "swing": {"bias": "buy", "confidence": "high", "entry": 3760.0, "target": 3900.0, "stop_loss": 3700.0, "reasoning": "Uptrend intact, low volatility supports 14-share sizing."},
            "long_term": {"bias": "buy", "confidence": "medium", "entry": None, "target": None, "stop_loss": None, "reasoning": "Sector bullish at +3.4% 1M momentum, structural uptrend."},
            "overall_summary": "Bullish across all horizons given sector, index, technical, and low-risk alignment.",
        })
    return "{}"


def run():
    with patch("agents.get_client", return_value=MagicMock()), \
         patch("agents.call_llm", side_effect=fake_call_llm), \
         patch("agents.fetch_news", return_value=FAKE_NEWS), \
         patch("agents.sector_momentum", return_value=FAKE_MOMENTUM), \
         patch("agents.technical_snapshot", return_value=FAKE_TECHNICAL):

        print("=== run_stock_analysis('TCS') ===")
        events = list(agents.run_stock_analysis("TCS"))
        for e in events:
            print(f"[{e['agent']:14}] {e['type']:6} {e['message']}")

        agent_names = [e["agent"] for e in events]
        assert "Risk" in agent_names, "Risk Agent did not run"
        assert "Technical" in agent_names
        assert "Decision" in agent_names

        final = events[-1]
        assert final["type"] == "final"
        assert final["data"]["decision"]["intraday"]["bias"] == "buy"
        assert final["data"]["risk"]["risk_label"] == "low"
        assert "confidence" in final["data"]["decision"]["swing"]
        print("\nFinal decision object:")
        print(json.dumps(final["data"]["decision"], indent=2))
        print("\nFinal risk object:")
        print(json.dumps(final["data"]["risk"], indent=2))

        print("\n=== run_market_overview() ===")
        events2 = list(agents.run_market_overview())
        for e in events2:
            print(f"[{e['agent']:14}] {e['type']:6} {e['message']}")
        assert events2[-1]["type"] == "final"
        assert len(events2[-1]["data"]["sector_outlooks"]) == 5

        print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run()
