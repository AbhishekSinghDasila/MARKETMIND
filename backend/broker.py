"""
Broker adapter interface.

PaperBrokerAdapter (used by default, everywhere in this app) just calls
portfolio.py — no real money, no real orders, ever.

ZerodhaKiteAdapter below is a documented STUB, not a working integration.
It exists so the *shape* of a real-broker integration is clear if you ever
want to build it, but every method deliberately raises NotImplementedError.

Turning a model's output into a real market order is a much bigger step
than anything else in this project — it requires a paid Kite Connect API
subscription, a KYC'd trading account, careful handling of access tokens,
and — critically — a manual human confirmation step before any live order,
since an LLM being "fairly confident" is not the same as being right. If
you build this out for real, add that confirmation step before anything
else, and paper-trade extensively first.
"""

from abc import ABC, abstractmethod

import portfolio as paper_portfolio


class BrokerAdapter(ABC):
    @abstractmethod
    def place_order(self, symbol: str, qty: int, side: str) -> dict:
        """side: 'BUY' or 'SELL'. Returns a dict describing the resulting order/trade."""
        ...

    @abstractmethod
    def get_positions(self) -> dict:
        ...


class PaperBrokerAdapter(BrokerAdapter):
    """The only adapter actually wired up to the app. Simulated trades only."""

    def place_order(self, symbol: str, qty: int, side: str) -> dict:
        if side.upper() == "BUY":
            return paper_portfolio.buy(symbol, qty)
        elif side.upper() == "SELL":
            return paper_portfolio.sell(symbol, qty)
        raise ValueError("side must be 'BUY' or 'SELL'")

    def get_positions(self) -> dict:
        return paper_portfolio.portfolio_snapshot()


class ZerodhaKiteAdapter(BrokerAdapter):
    """
    STUB ONLY — not implemented, not wired up anywhere in this app.

    To actually build this out, you would:
      1. pip install kiteconnect, register an app at https://developers.kite.trade
         (requires a paid Kite Connect subscription).
      2. Implement the login flow to obtain a daily access_token.
      3. In place_order(), call self.kite.place_order(...) with real
         tradingsymbol/exchange/transaction_type/quantity/order_type params.
      4. Add a mandatory confirmation step (e.g. a UI "are you sure" dialog,
         or a max-order-value cap) BEFORE any call reaches place_order() —
         do not let the Decision Agent's output reach this class directly.
    """

    def __init__(self, api_key: str, access_token: str):
        raise NotImplementedError(
            "ZerodhaKiteAdapter is an intentional stub. Wiring up real order "
            "execution is a deliberate, separate decision — see the class "
            "docstring before implementing this."
        )

    def place_order(self, symbol: str, qty: int, side: str) -> dict:
        raise NotImplementedError

    def get_positions(self) -> dict:
        raise NotImplementedError


# The only adapter actually used by main.py right now.
active_broker: BrokerAdapter = PaperBrokerAdapter()
