# MarketMind — Multi-Agent Stock Intelligence (educational project)

**This is a research/educational tool, not investment advice.** No system —
including this one — can reliably predict market movements. Every trade this
app makes is a *paper trade* (simulated, virtual money only). Nothing here
places a real order. Do your own research and consult a licensed financial
advisor before making real investment decisions.

## What this is

Eight agents collaborate to analyze the Indian stock market (NSE/BSE,
Nifty/Sensex):

```
                    ┌──────────────┐
                    │  News Agent  │  free RSS feeds -> LLM tags each
                    │              │  article by sector + sentiment
                    └──────┬───────┘
                           │
        ┌──────────┬───────┼───────┬──────────┐
        ▼          ▼       ▼       ▼          ▼
   [Banking]     [IT]   [FMCG]  [Oil&Gas]  [Pharma]     5 Sector Agents —
   Sector        Sector  Sector  Sector     Sector       real price momentum
   Agent         Agent   Agent   Agent      Agent        + relevant news
        │          │       │       │          │
        └──────────┴───────┼───────┴──────────┘
                           ▼
                    ┌──────────────┐
                    │ Index Agent  │  Nifty/Sensex technicals +
                    │ (Nifty/      │  all sector views + macro news
                    │  Sensex)     │  -> overall market view
                    └──────┬───────┘
                           │           (only for single-stock analysis)
                           ▼
                  ┌──────────────────┐
                  │ Technical Agent  │  REAL support/resistance,
                  │                  │  RSI, MACD, moving averages
                  └────────┬─────────┘  (pandas math, not LLM guesses)
                           ▼
                  ┌──────────────────┐
                  │ Decision Agent   │  intraday / swing / long-term
                  │                  │  buy/sell/hold + entry/target/
                  └────────┬─────────┘  stop-loss (from real levels only)
                           ▼
                  ┌──────────────────┐
                  │ Paper Portfolio  │  simulated buy/sell, P&L tracking
                  └──────────────────┘
```

**The one rule that matters most in this codebase:** every price number —
support/resistance levels, RSI, MACD, entry/target/stop-loss — comes from
real math on real historical data in `data.py`. LLM agents are only ever
given already-computed numbers to explain or choose from; they never invent
one. See `agents.py`'s `decision_agent()` docstring/prompt for how this is
enforced.

## Two ways to use it

1. **Market Overview** — no stock needed. Runs the News Agent + all 5 Sector
   Agents + the Index Agent to produce a sector-by-sector market dashboard.
2. **Analyze a Stock** — give it a symbol (e.g. `RELIANCE`, `TCS`,
   `HDFCBANK`, or an index like `^NSEI`). Runs the full pipeline down to a
   Decision Agent call across three trading horizons.

Both stream live via Server-Sent Events, same pattern as the AgentX project
this was built after — you watch each agent hand off to the next.

## Tech stack

- Backend: FastAPI + Groq (`llama-3.3-70b-versatile`, free tier, no card)
- Price data: `yfinance` (free, no key — NSE via `.NS` suffix, indices via `^NSEI`/`^BSESN`)
- Technical analysis: `pandas` + `ta` (real indicator math)
- News: RSS feeds via `feedparser` (Economic Times, Moneycontrol, LiveMint, Business Standard)
- Paper trading: a simple JSON-file-backed portfolio (`portfolio.py`) — no real broker
- Frontend: Next.js 16 (App Router) + TypeScript
- Deploy: Render (backend) + Vercel (frontend), both free tier

## Project structure

```
backend/
├── main.py          FastAPI app: SSE endpoints + portfolio REST endpoints
├── agents.py         News/Sector/Index/Technical/Decision agents + orchestrators
├── data.py           yfinance price fetching + deterministic technical analysis
├── news.py           Free RSS news fetching
├── portfolio.py       Paper trading: buy/sell/P&L, JSON-file persisted
├── broker.py          BrokerAdapter interface — paper trading is the live
│                      default; a real-broker (Zerodha Kite) integration is
│                      a documented, disabled stub — see the file's docstring
├── test_pipeline.py   Mocked end-to-end test of both agent orchestrators
├── test_portfolio.py  Tests of the paper trading buy/sell/P&L math
├── requirements.txt
├── render.yaml
└── .env.example

frontend/
├── app/
│   ├── page.tsx                 Tab shell + disclaimer banner
│   ├── components/
│   │   ├── MarketOverview.tsx    Sector-by-sector dashboard tab
│   │   ├── StockAnalysis.tsx     Full pipeline map for one stock + paper trade buttons
│   │   └── Portfolio.tsx         Holdings, P&L, trade history, manual trade form
│   ├── lib/types.ts              Shared TypeScript types + SSE stream helper
│   ├── layout.tsx, globals.css
├── package.json, tsconfig.json, next.config.js
└── .env.example
```

## 1. Get a free Groq API key

Go to https://console.groq.com, sign up (no card needed), and create an API
key under **API Keys**.

## 2. Run it locally

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your GROQ_API_KEY
uvicorn main:app --reload
```
Check `http://localhost:8000/docs` for the interactive API docs.

**Frontend** (new terminal)
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
Open `http://localhost:3000`.

**Run the tests** (optional but recommended before deploying):
```bash
cd backend
python test_pipeline.py     # mocked end-to-end agent pipeline test
python test_portfolio.py    # paper trading math test
```

## 3. Deploy the backend on Render

Same process as before:
1. New Web Service → connect your repo → root directory `backend`.
2. Render should auto-detect `render.yaml` (already pinned to Python 3.11.9
   — a newer default Python version can fail to build `pydantic`/`pandas`
   from source; this avoids that).
3. Add environment variables: `GROQ_API_KEY`, `GROQ_MODEL`, `ALLOWED_ORIGINS`
   (set this to your Vercel URL once you have it), `STARTING_CASH`.
4. Deploy, note the URL.

## 4. Deploy the frontend on Vercel

1. Add New Project → same repo → root directory `frontend`.
2. Environment variable: `NEXT_PUBLIC_API_URL` = your Render URL.
3. Deploy, note the URL.
4. Go back to Render and update `ALLOWED_ORIGINS` to that exact Vercel URL.

## Known limitations

- `yfinance` is an unofficial wrapper around Yahoo Finance data — it can
  occasionally be slow, rate-limited, or briefly break if Yahoo changes
  something server-side. Same "free tool, occasional flakiness" trade-off
  as AgentX's DuckDuckGo search.
- The paper portfolio is stored in a single JSON file, not a database — fine
  for a demo/portfolio project, but it resets on Render redeploys and isn't
  multi-user safe (everyone hitting the deployed instance shares one
  portfolio). A real version of this would need per-user accounts and a
  proper database.
- Sector classification only covers the 25 large-cap stocks in the 5
  baskets (`data.py`'s `SECTOR_TICKERS`) — analyzing any other stock still
  runs Technical + Decision agents, just skips the Sector Agent step.
- Groq's free tier is rate-limited (~30 requests/minute). A full stock
  analysis makes about 4-5 LLM calls; a market overview makes about 7
  (1 news + 5 sector + 1 index) — comfortable within the limit for normal
  use, but rapid repeated runs could briefly hit a 429.
- This system cannot and does not "correctly predict" anything — it
  produces a structured, explainable view grounded in real news and real
  technical levels. Treat every output as one input into your own
  decision-making, never as a guarantee.
