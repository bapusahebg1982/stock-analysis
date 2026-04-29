from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Backend running"}


# 🔍 Auto ticker fix (India support)
def normalize_ticker(ticker: str):
    ticker = ticker.upper()
    if "." not in ticker:
        # Try US first, fallback India
        test = yf.Ticker(ticker).history(period="5d")
        if test.empty:
            ticker = ticker + ".NS"
    return ticker


# RSI
def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# 🔎 Get sector
def get_sector(stock):
    try:
        info = stock.info
        return info.get("sector", "Unknown")
    except:
        return "Unknown"


# 🧠 Analysis
def analyze_stock(raw_ticker):
    ticker = normalize_ticker(raw_ticker)

    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")

    if df.empty or len(df) < 50:
        return None

    price = float(df["Close"].iloc[-1])

    df["RSI"] = compute_rsi(df)
    rsi = float(df["RSI"].iloc[-1])

    ma50 = float(df["Close"].rolling(50).mean().iloc[-1])
    ma200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

    # Score
    score = 50
    reasons = []

    # RSI
    if rsi < 30:
        score += 20
        reasons.append("Oversold (RSI < 30)")
    elif rsi > 70:
        score -= 20
        reasons.append("Overbought (RSI > 70)")

    # Trend
    if price > ma50:
        score += 10
        reasons.append("Above 50-day MA (bullish)")
    if ma200 and price > ma200:
        score += 10
        reasons.append("Above 200-day MA (long-term strength)")

    score = max(0, min(100, int(score)))

    # Recommendation
    if score >= 75:
        short_term = "Bullish momentum"
        long_term = "Strong trend continuation"
    elif score >= 60:
        short_term = "Neutral / wait for breakout"
        long_term = "Stable but not strong"
    else:
        short_term = "Weak momentum"
        long_term = "Potential downside risk"

    sector = get_sector(stock)

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "score": score,
        "sector": sector,
        "technicals": {
            "rsi": round(rsi, 2),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2) if ma200 else None
        },
        "insights": {
            "short_term": short_term,
            "long_term": long_term,
            "reasons": reasons
        }
    }


# 🔁 Peer finder (dynamic-ish)
SECTOR_PEERS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA"],
    "Financial Services": ["JPM", "BAC", "HDFCBANK.NS"],
    "Energy": ["XOM", "CVX", "RELIANCE.NS"],
    "Consumer Cyclical": ["AMZN", "TSLA"],
}


def get_peers(sector):
    return SECTOR_PEERS.get(sector, [])


@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    try:
        main = analyze_stock(ticker)

        if not main:
            return {"error": "Ticker not found or insufficient data"}

        peers = get_peers(main["sector"])

        peer_results = []
        for p in peers:
            if p != main["ticker"]:
                res = analyze_stock(p)
                if res:
                    peer_results.append(res)

        peer_results = sorted(peer_results, key=lambda x: x["score"], reverse=True)

        return {
            "stock": main,
            "peers": peer_results[:5]
        }

    except Exception as e:
        return {"error": str(e)}


# 🧠 Recommendations
@app.get("/recommendations")
def recommendations():
    universe = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "INFY.NS", "RELIANCE.NS"]

    results = []
    for t in universe:
        res = analyze_stock(t)
        if res:
            results.append(res)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return {"top_picks": results[:5]}
