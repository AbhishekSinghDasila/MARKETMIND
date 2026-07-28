"""
Paper trading portfolio — tracks hypothetical trades and P&L. No real money,
no real broker, ever, from this module. Persisted to a simple JSON file so
a demo session survives a server restart; on Render's free tier this file
lives on ephemeral disk and resets on redeploy, which is a fine trade-off
for a portfolio project (see README) but worth knowing if you extend this.
"""

import json
import os
import time

from data import get_last_price

PORTFOLIO_FILE = os.getenv("PORTFOLIO_FILE", "portfolio.json")
STARTING_CASH = float(os.getenv("STARTING_CASH", "1000000"))  # ₹10,00,000 virtual cash


def _default_portfolio() -> dict:
    return {"cash": STARTING_CASH, "holdings": {}, "trade_history": []}


def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return _default_portfolio()
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return _default_portfolio()


def save_portfolio(portfolio: dict) -> None:
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


def reset_portfolio() -> dict:
    portfolio = _default_portfolio()
    save_portfolio(portfolio)
    return portfolio


def buy(symbol: str, qty: int) -> dict:
    if qty <= 0:
        raise ValueError("Quantity must be positive")
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.startswith("^"):
        symbol = f"{symbol}.NS"

    price = get_last_price(symbol)
    cost = price * qty
    portfolio = load_portfolio()
    if cost > portfolio["cash"]:
        raise ValueError(f"Insufficient virtual cash: need ₹{cost:,.2f}, have ₹{portfolio['cash']:,.2f}")

    holding = portfolio["holdings"].get(symbol, {"qty": 0, "avg_price": 0.0})
    new_qty = holding["qty"] + qty
    new_avg = (holding["qty"] * holding["avg_price"] + qty * price) / new_qty
    portfolio["holdings"][symbol] = {"qty": new_qty, "avg_price": round(new_avg, 2)}
    portfolio["cash"] = round(portfolio["cash"] - cost, 2)
    portfolio["trade_history"].append({
        "type": "BUY", "symbol": symbol, "qty": qty, "price": price,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_portfolio(portfolio)
    return portfolio


def sell(symbol: str, qty: int) -> dict:
    if qty <= 0:
        raise ValueError("Quantity must be positive")
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.startswith("^"):
        symbol = f"{symbol}.NS"

    portfolio = load_portfolio()
    holding = portfolio["holdings"].get(symbol)
    if not holding or holding["qty"] < qty:
        have = holding["qty"] if holding else 0
        raise ValueError(f"Cannot sell {qty} of {symbol}: only hold {have}")

    price = get_last_price(symbol)
    proceeds = price * qty
    realized_pnl = round((price - holding["avg_price"]) * qty, 2)

    holding["qty"] -= qty
    if holding["qty"] == 0:
        del portfolio["holdings"][symbol]
    else:
        portfolio["holdings"][symbol] = holding

    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)
    portfolio["trade_history"].append({
        "type": "SELL", "symbol": symbol, "qty": qty, "price": price,
        "realized_pnl": realized_pnl, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_portfolio(portfolio)
    return portfolio


def portfolio_snapshot() -> dict:
    """Current portfolio plus live valuation and unrealized P&L per holding."""
    portfolio = load_portfolio()
    holdings_detail = []
    total_holdings_value = 0.0
    for symbol, h in portfolio["holdings"].items():
        try:
            current_price = get_last_price(symbol)
        except Exception:
            current_price = h["avg_price"]  # fail soft if a quote lookup breaks
        value = round(current_price * h["qty"], 2)
        unrealized_pnl = round((current_price - h["avg_price"]) * h["qty"], 2)
        total_holdings_value += value
        holdings_detail.append({
            "symbol": symbol, "qty": h["qty"], "avg_price": h["avg_price"],
            "current_price": current_price, "value": value, "unrealized_pnl": unrealized_pnl,
        })

    total_value = round(portfolio["cash"] + total_holdings_value, 2)
    realized_pnl = round(sum(t.get("realized_pnl", 0) for t in portfolio["trade_history"]), 2)

    return {
        "cash": portfolio["cash"],
        "holdings": holdings_detail,
        "total_holdings_value": round(total_holdings_value, 2),
        "total_portfolio_value": total_value,
        "starting_cash": STARTING_CASH,
        "total_return_pct": round((total_value / STARTING_CASH - 1) * 100, 2),
        "realized_pnl": realized_pnl,
        "trade_history": list(reversed(portfolio["trade_history"][-50:])),
    }
