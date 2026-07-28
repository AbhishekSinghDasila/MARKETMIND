"""
MarketMind — multi-agent stock intelligence system.

Six agents:
  1. News Agent       — tags real RSS headlines by sector + sentiment
  2. Sector Agents (5) — Banking/IT/FMCG/Oil&Gas/Pharma, momentum + news
  3. Index Agent      — Nifty/Sensex overall view
  4. Technical Agent  — narrates already-computed support/resistance/RSI/MACD
  5. Risk Agent       — narrates already-computed volatility + position sizing
  6. Decision Agent   — combines everything into intraday/swing/long-term calls

Two pipelines:
  run_market_overview()   -> News + all 5 Sector Agents + Index Agent
  run_stock_analysis(sym) -> News + Sector + Index + Technical + Risk + Decision

Hard rule throughout: every price/quantitative number (support, resistance,
RSI, MACD, ATR, volatility %, position size, entry/target/stop-loss) comes
from data.py's real math. Agents are only ever allowed to select from and
explain those numbers — never invent new ones. Every prompt below also
requires agents to cite the SPECIFIC numbers they were given rather than
write generic filler ("momentum looks positive") — vague reasoning that
doesn't reference an actual figure is treated as a failure mode here, the
same way it was in the AgentX project's Writer agent.
"""

import json
import os
from typing import Iterator

from openai import OpenAI

from data import (
    SECTOR_TICKERS, INDEX_TICKERS, TICKER_SECTOR, sector_momentum,
    technical_snapshot, technical_snapshot_safe,
)
from news import fetch_news

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def get_client() -> OpenAI:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set on the server")
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def call_llm(client, system, user, json_mode=False, max_tokens=900, temperature=0.4):
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# 1. News Agent
# ---------------------------------------------------------------------------


def news_agent(client) -> list[dict]:
    raw_items = fetch_news(max_per_feed=8)
    listing = "\n".join(
        f"{i}. [{it['source']}] {it['title']} — {it['summary'][:180]}"
        for i, it in enumerate(raw_items)
        if it["title"] != "feed_error"
    )
    system = (
        "You are the News Agent in a stock market analysis system. You are given "
        "a numbered list of real financial news headlines. For EACH item, tag it with:\n"
        "- sector: one of BANKING, IT, FMCG, OIL_GAS, PHARMA, MACRO (RBI policy, "
        "inflation, global markets, currency, broad economy), or OTHER (unrelated to "
        "Indian equity markets — sports, entertainment, etc.)\n"
        "- sentiment: bullish, bearish, or neutral, from the perspective of the sector/"
        "market it affects — not the general tone of the headline\n"
        "- impact: high, medium, or low — how much this is likely to actually move "
        "prices, vs routine/incremental news\n"
        "- reason: one short, specific phrase naming the actual mechanism (e.g. "
        "'rate cut lowers bank funding costs', not 'positive for banks')\n"
        'Respond ONLY with JSON: {"tags": [{"index": 0, "sector": "...", "sentiment": "...", '
        '"impact": "...", "reason": "..."}, ...]} with exactly one entry per numbered item, in order.'
    )
    raw = call_llm(client, system, listing, json_mode=True, max_tokens=2000)
    try:
        tags = json.loads(raw).get("tags", [])
    except Exception:
        tags = []

    tagged = []
    valid_items = [it for it in raw_items if it["title"] != "feed_error"]
    for tag in tags:
        idx = tag.get("index")
        if idx is None or idx >= len(valid_items):
            continue
        item = valid_items[idx]
        tagged.append({**item, **tag})
    return tagged


# ---------------------------------------------------------------------------
# 2. Sector Agents
# ---------------------------------------------------------------------------


def sector_agent(client, sector: str, tagged_news: list[dict]) -> dict:
    momentum = sector_momentum(sector)
    # High-impact news first, so the model weighs materially significant items
    # over routine ones if it has to trim.
    relevant_news = sorted(
        [n for n in tagged_news if n.get("sector") == sector],
        key=lambda n: {"high": 0, "medium": 1, "low": 2}.get(n.get("impact"), 3),
    )[:6]
    news_text = (
        "\n".join(f"- [{n.get('impact','?')} impact, {n['sentiment']}] {n['title']} — {n.get('reason','')}" for n in relevant_news)
        or "No sector-specific news today."
    )

    system = (
        f"You are the {sector} Sector Agent. You are given real price momentum data "
        f"for this sector's basket of large-cap stocks, plus news tagged as relevant "
        f"to this sector.\n\n"
        "Requirements for your reasoning:\n"
        "- Cite the ACTUAL momentum numbers you were given (e.g. '5-day momentum of "
        "+1.8% led by X') — never write generic filler like 'momentum looks positive' "
        "without a number attached.\n"
        "- If per-stock momentum diverges meaningfully (some stocks up, others down), "
        "say so explicitly rather than only reporting the average.\n"
        "- Weigh high-impact news more heavily than low-impact news in your outlook.\n"
        'Respond ONLY with JSON: {"outlook": "bullish"|"bearish"|"neutral", '
        '"confidence": "low"|"medium"|"high", "reasoning": "2-3 sentences citing specific '
        'numbers and news given"}'
    )
    user = (
        f"5-day avg momentum: {momentum['avg_change_5d_pct']}%\n"
        f"1-month avg momentum: {momentum['avg_change_1m_pct']}%\n"
        f"Per-stock 5-day change: {momentum['stocks']}\n\n"
        f"Relevant news (sorted by impact):\n{news_text}"
    )
    raw = call_llm(client, system, user, json_mode=True, max_tokens=450)
    try:
        result = json.loads(raw)
    except Exception:
        result = {"outlook": "neutral", "confidence": "low", "reasoning": "Could not parse model output."}
    result["sector"] = sector
    result["momentum"] = momentum
    result["news_used"] = relevant_news
    return result


# ---------------------------------------------------------------------------
# 3. Index Agent
# ---------------------------------------------------------------------------


def index_agent(client, sector_outlooks: list[dict], tagged_news: list[dict]) -> dict:
    macro_news = sorted(
        [n for n in tagged_news if n.get("sector") == "MACRO"],
        key=lambda n: {"high": 0, "medium": 1, "low": 2}.get(n.get("impact"), 3),
    )[:6]
    macro_text = (
        "\n".join(f"- [{n.get('impact','?')} impact, {n['sentiment']}] {n['title']} — {n.get('reason','')}" for n in macro_news)
        or "No major macro news today."
    )
    sector_summary = "\n".join(
        f"- {s['sector']}: {s['outlook']} ({s['confidence']} confidence) — {s['reasoning']}" for s in sector_outlooks
    )

    nifty_tech = technical_snapshot_safe(INDEX_TICKERS["NIFTY50"])
    sensex_tech = technical_snapshot_safe(INDEX_TICKERS["SENSEX"])

    system = (
        "You are the Index Agent, giving an overall Nifty/Sensex market view. You are "
        "given real technical data for both indices, every sector agent's outlook, and "
        "macro news. Occasionally the index technical data may be unavailable (current_price "
        "will be null) — if so, say so plainly and lean more heavily on the sector outlooks "
        "and macro news instead of guessing index numbers.\n\n"
        "Requirements: when index data IS available, cite the actual index RSI/trend values "
        "and reference at least one specific sector outlook by name — do not write a generic "
        "'markets look mixed' summary without pointing to what's actually driving that view. "
        "If sector outlooks conflict with each other, say which ones and why that creates "
        "uncertainty rather than averaging it away silently.\n"
        'Respond ONLY with JSON: {"overall_view": "bullish"|"bearish"|"neutral", '
        '"reasoning": "3-4 sentences referencing specific sector outlooks and index technicals given"}'
    )
    user = (
        f"Nifty 50: price {nifty_tech['current_price']}, trend {nifty_tech['trend']}, RSI {nifty_tech['rsi_14']}, MACD {nifty_tech['macd_bias']}\n"
        f"Sensex: price {sensex_tech['current_price']}, trend {sensex_tech['trend']}, RSI {sensex_tech['rsi_14']}, MACD {sensex_tech['macd_bias']}\n\n"
        f"Sector outlooks:\n{sector_summary}\n\nMacro news (sorted by impact):\n{macro_text}"
    )
    raw = call_llm(client, system, user, json_mode=True, max_tokens=550)
    try:
        result = json.loads(raw)
    except Exception:
        result = {"overall_view": "neutral", "reasoning": "Could not parse model output."}
    result["nifty"] = nifty_tech
    result["sensex"] = sensex_tech
    return result


# ---------------------------------------------------------------------------
# 4. Technical Agent (numbers are already computed in data.py)
# ---------------------------------------------------------------------------


def technical_agent(client, symbol: str) -> dict:
    snap = technical_snapshot(symbol)
    system = (
        "You are the Technical Agent. You are given already-computed support/resistance "
        "levels, moving averages, RSI, and MACD for a stock — real numbers from real price "
        "history. Do NOT invent or adjust any number.\n\n"
        "Explain what this technical picture suggests: trend strength (cite the actual "
        "SMA values and their ordering), whether RSI's specific value indicates overbought "
        "(>70) / oversold (<30) / neutral, and whether MACD confirms or contradicts the "
        "trend. If signals conflict (e.g. uptrend but RSI overbought), say so explicitly — "
        "that conflict is itself useful information, not something to smooth over.\n"
        'Respond ONLY with JSON: {"narrative": "3-4 sentences citing the specific numbers given"}'
    )
    raw = call_llm(client, system, json.dumps(snap), json_mode=True, max_tokens=400)
    try:
        narrative = json.loads(raw).get("narrative", "")
    except Exception:
        narrative = ""
    snap["narrative"] = narrative
    return snap


# ---------------------------------------------------------------------------
# 5. Risk Agent (volatility + position sizing are already computed in data.py)
# ---------------------------------------------------------------------------


def risk_agent(client, symbol: str, technical: dict) -> dict:
    """Narrates the already-computed ATR-based volatility and fixed-fractional
    position-sizing numbers. The sizing math itself (1% risk of a ₹1,00,000
    reference position, 1.5×ATR stop distance) lives in data.py — this agent
    never invents or adjusts the number, only explains what it means and
    flags when caution is warranted."""
    system = (
        "You are the Risk Agent. You are given a stock's ATR-based volatility and a "
        "position-sizing suggestion already computed for a ₹1,00,000 reference position "
        "risking 1% of that capital per trade, with a stop distance of 1.5x ATR. This is "
        "the standard 'fixed-fractional' position sizing rule used in real risk "
        "management — you are not inventing this method, just explaining these specific "
        "numbers.\n\n"
        "Explain in plain terms: what the volatility label means for how tightly this "
        "stock tends to move, and what the suggested share quantity implies about "
        "position size relative to the stop distance. If risk_label is 'high', "
        "explicitly recommend a wider stop or smaller position than usual and say why. "
        "If ATR/volatility data is missing (null), say the risk picture is incomplete "
        "rather than guessing.\n"
        'Respond ONLY with JSON: {"risk_summary": "2-3 sentences citing the specific '
        'ATR/volatility/position-size numbers given"}'
    )
    risk_fields = {
        "symbol": symbol,
        "atr_14": technical.get("atr_14"),
        "volatility_pct": technical.get("volatility_pct"),
        "risk_label": technical.get("risk_label"),
        "suggested_position_qty": technical.get("suggested_position_qty"),
        "reference_capital": technical.get("reference_capital"),
        "risk_pct_per_trade": technical.get("risk_pct_per_trade"),
        "current_price": technical.get("current_price"),
    }
    raw = call_llm(client, system, json.dumps(risk_fields), json_mode=True, max_tokens=300)
    try:
        summary = json.loads(raw).get("risk_summary", "")
    except Exception:
        summary = ""
    return {**risk_fields, "risk_summary": summary}


# ---------------------------------------------------------------------------
# 6. Decision Agent
# ---------------------------------------------------------------------------


def decision_agent(
    client, symbol: str, sector_outlook: dict | None, index_view: dict, technical: dict, risk: dict
) -> dict:
    system = (
        "You are the Decision Agent. Combine the sector outlook, overall market view, "
        "technical levels, and risk/position-sizing data into a trading view for THREE "
        "horizons: intraday, swing (days to a few weeks), and long_term (months+).\n\n"
        "CRITICAL RULES:\n"
        "- For entry, target, and stop_loss in every horizon, you MUST pick actual "
        "numbers from the provided support_levels / resistance_levels / current_price — "
        "never invent a price. If you don't have a sensible level for a field, use null.\n"
        "- Every horizon's reasoning must cite at least one specific number from the "
        "inputs (an RSI value, a momentum %, a support/resistance price, the volatility "
        "label) — generic reasoning like 'looks favorable' without a number is not "
        "acceptable.\n"
        "- The three horizons can and often should disagree with each other (e.g. "
        "bullish long-term but overbought for an intraday entry) — do not force them to "
        "agree if the evidence doesn't support that.\n"
        "- Factor the risk data into at least the swing and long_term reasoning (e.g. "
        "mention the suggested position size or volatility label where relevant).\n"
        "- confidence per horizon should reflect how much the sector/index/technical/risk "
        "signals actually agree with each other — 'high' only when they align.\n\n"
        'Respond ONLY with JSON:\n'
        '{"intraday": {"bias": "buy"|"sell"|"hold", "confidence": "low"|"medium"|"high", '
        '"entry": number|null, "target": number|null, "stop_loss": number|null, '
        '"reasoning": "1-2 sentences citing specific numbers"}, '
        '"swing": {same shape}, "long_term": {same shape}, '
        '"overall_summary": "2-3 sentences tying it all together, noting any disagreement between horizons"}'
    )
    user = (
        f"Symbol: {symbol}\n"
        f"Sector outlook: {json.dumps(sector_outlook) if sector_outlook else 'N/A — sector not classified'}\n"
        f"Market/index view: {json.dumps({'overall_view': index_view.get('overall_view'), 'reasoning': index_view.get('reasoning')})}\n"
        f"Technical snapshot: {json.dumps(technical)}\n"
        f"Risk/position sizing: {json.dumps(risk)}"
    )
    raw = call_llm(client, system, user, json_mode=True, max_tokens=1000)
    try:
        return json.loads(raw)
    except Exception:
        return {"error": "Could not parse decision output", "raw": raw}


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------


def run_market_overview() -> Iterator[dict]:
    client = get_client()

    yield {"agent": "News", "type": "start", "message": "Fetching and tagging today's financial news"}
    tagged_news = news_agent(client)
    yield {"agent": "News", "type": "result", "message": f"Tagged {len(tagged_news)} articles", "data": tagged_news}

    sector_outlooks = []
    for sector in SECTOR_TICKERS:
        yield {"agent": f"Sector:{sector}", "type": "start", "message": f"Analyzing {sector} sector"}
        outlook = sector_agent(client, sector, tagged_news)
        sector_outlooks.append(outlook)
        yield {"agent": f"Sector:{sector}", "type": "result", "message": f"{sector} outlook: {outlook['outlook']}", "data": outlook}

    yield {"agent": "Index", "type": "start", "message": "Synthesizing overall Nifty/Sensex view"}
    index_view = index_agent(client, sector_outlooks, tagged_news)
    yield {"agent": "Index", "type": "result", "message": f"Overall view: {index_view['overall_view']}", "data": index_view}

    yield {"agent": "System", "type": "final", "message": "Market overview complete", "data": {
        "sector_outlooks": sector_outlooks, "index_view": index_view,
    }}


def run_stock_analysis(symbol: str) -> Iterator[dict]:
    client = get_client()
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and symbol not in INDEX_TICKERS.values():
        symbol = f"{symbol}.NS"

    yield {"agent": "News", "type": "start", "message": "Fetching and tagging today's financial news"}
    tagged_news = news_agent(client)
    yield {"agent": "News", "type": "result", "message": f"Tagged {len(tagged_news)} articles", "data": tagged_news}

    sector = TICKER_SECTOR.get(symbol)
    sector_outlook = None
    if sector:
        yield {"agent": f"Sector:{sector}", "type": "start", "message": f"Analyzing {sector} sector for {symbol}"}
        sector_outlook = sector_agent(client, sector, tagged_news)
        yield {"agent": f"Sector:{sector}", "type": "result", "message": f"{sector} outlook: {sector_outlook['outlook']}", "data": sector_outlook}
    else:
        yield {"agent": "Sector", "type": "result", "message": f"{symbol} isn't in a classified sector basket — skipping sector view", "data": None}

    all_sector_outlooks = [sector_outlook] if sector_outlook else []
    yield {"agent": "Index", "type": "start", "message": "Synthesizing overall Nifty/Sensex view"}
    index_view = index_agent(client, all_sector_outlooks, tagged_news)
    yield {"agent": "Index", "type": "result", "message": f"Overall view: {index_view['overall_view']}", "data": index_view}

    yield {"agent": "Technical", "type": "start", "message": f"Computing support/resistance and indicators for {symbol}"}
    technical = technical_agent(client, symbol)
    yield {"agent": "Technical", "type": "result", "message": "Technical snapshot ready", "data": technical}

    yield {"agent": "Risk", "type": "start", "message": f"Assessing volatility and position sizing for {symbol}"}
    risk = risk_agent(client, symbol, technical)
    yield {"agent": "Risk", "type": "result", "message": f"Risk level: {risk['risk_label']}", "data": risk}

    yield {"agent": "Decision", "type": "start", "message": "Combining everything into a trade plan"}
    decision = decision_agent(client, symbol, sector_outlook, index_view, technical, risk)
    yield {"agent": "Decision", "type": "result", "message": "Decision ready", "data": decision}

    yield {"agent": "System", "type": "final", "message": "Analysis complete", "data": {
        "symbol": symbol, "sector_outlook": sector_outlook, "index_view": index_view,
        "technical": technical, "risk": risk, "decision": decision,
    }}