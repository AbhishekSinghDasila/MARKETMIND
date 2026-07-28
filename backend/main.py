import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents import run_market_overview, run_stock_analysis
from broker import active_broker
import data
import portfolio as paper_portfolio

load_dotenv()

app = FastAPI(title="MarketMind API")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    symbol: str


class TradeRequest(BaseModel):
    symbol: str
    qty: int


@app.get("/")
def health():
    return {"status": "ok", "service": "MarketMind API"}


def sse_stream(generator):
    def event_stream():
        try:
            for step in generator:
                yield f"data: {json.dumps(step)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'agent': 'System', 'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/market-overview")
def market_overview():
    """Streams News + all 5 Sector Agents + Index Agent as SSE events."""
    return sse_stream(run_market_overview())


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Streams the full News->Sector->Index->Technical->Decision pipeline for one stock."""
    return sse_stream(run_stock_analysis(req.symbol))


@app.get("/api/live/{symbol}")
def live_chart(symbol: str):
    """Recent intraday candles for a live-updating chart. Polled every ~30s by the frontend."""
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.startswith("^"):
        symbol = f"{symbol}.NS"
    try:
        return data.intraday_history(symbol)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/ticker")
def ticker():
    """Fast Nifty/Sensex quotes for the frontend's ticker tape — no LLM calls."""
    return data.index_quotes()


@app.get("/api/portfolio")
def get_portfolio():
    return paper_portfolio.portfolio_snapshot()


@app.post("/api/portfolio/buy")
def portfolio_buy(req: TradeRequest):
    try:
        active_broker.place_order(req.symbol, req.qty, "BUY")
        return paper_portfolio.portfolio_snapshot()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/portfolio/sell")
def portfolio_sell(req: TradeRequest):
    try:
        active_broker.place_order(req.symbol, req.qty, "SELL")
        return paper_portfolio.portfolio_snapshot()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/portfolio/reset")
def portfolio_reset():
    return paper_portfolio.reset_portfolio()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
