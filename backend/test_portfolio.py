import os
from unittest.mock import patch

os.environ["PORTFOLIO_FILE"] = "/tmp/test_portfolio.json"
os.environ["STARTING_CASH"] = "100000"

import importlib
import portfolio
importlib.reload(portfolio)  # pick up the env vars set above

prices = {"TCS.NS": 3800.0, "RELIANCE.NS": 2900.0}


def fake_price(symbol):
    return prices[symbol]


with patch("portfolio.get_last_price", side_effect=fake_price):
    portfolio.reset_portfolio()

    # Buy 10 TCS at 3800 -> cost 38000, cash should drop to 62000
    p = portfolio.buy("TCS", 10)
    assert p["cash"] == 100000 - 38000, p["cash"]
    assert p["holdings"]["TCS.NS"]["qty"] == 10
    assert p["holdings"]["TCS.NS"]["avg_price"] == 3800.0
    print("Buy 1 OK — cash:", p["cash"])

    # Buy 5 more TCS at same price -> avg price should stay 3800, qty 15
    p = portfolio.buy("TCS", 5)
    assert p["holdings"]["TCS.NS"]["qty"] == 15
    assert p["holdings"]["TCS.NS"]["avg_price"] == 3800.0
    print("Buy 2 OK — qty:", p["holdings"]["TCS.NS"]["qty"])

    # Try to buy more than affordable -> should raise
    try:
        portfolio.buy("RELIANCE", 1000)  # 1000*2900 = 2.9M, way over cash
        raise AssertionError("Should have raised on insufficient funds")
    except ValueError as e:
        print("Insufficient funds correctly rejected:", e)

    # Price moves up, sell 10 TCS at new price 4000 -> realized pnl = (4000-3800)*10 = 2000
    prices["TCS.NS"] = 4000.0
    p = portfolio.sell("TCS", 10)
    assert p["holdings"]["TCS.NS"]["qty"] == 5
    last_trade = p["trade_history"][-1]
    assert last_trade["realized_pnl"] == 2000.0, last_trade
    print("Sell OK — realized P&L:", last_trade["realized_pnl"])

    # Try to sell more than held -> should raise
    try:
        portfolio.sell("TCS", 100)
        raise AssertionError("Should have raised on overselling")
    except ValueError as e:
        print("Oversell correctly rejected:", e)

    snap = portfolio.portfolio_snapshot()
    print("\nFinal snapshot:")
    print("  cash:", snap["cash"])
    print("  total_portfolio_value:", snap["total_portfolio_value"])
    print("  realized_pnl:", snap["realized_pnl"])
    print("  holdings:", snap["holdings"])

print("\nALL PORTFOLIO ASSERTIONS PASSED")
