from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd

app = FastAPI()

# CORS
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


# RSI
def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# Analyze single stock
def analyze_stock(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")

    if df.empty or len(df) < 50:
        return None

    price = float(df["Close"].iloc[-1])

    df["RSI"] = compute_rsi(df)
    rsi = float(df["RSI"].iloc[-1])

    ma50 = float(df["Close"].rolling(50).mean().iloc[-1])

    score = 50

    if rsi < 30:
        score += 20
    elif rsi > 70:
        score -= 20

    if price > ma50:
        score += 10

    score = max(0, min(100, int(score)))

    # AI Recommendation label
    if score >= 75:
        rec = "BUY"
    elif score >= 60:
        rec = "HOLD"
    else:
        rec = "AVOID"

    return {
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "score": score,
        "recommendation": rec
    }


# MAIN ANALYZE
@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    try:
        result = analyze_stock(ticker)
        if not result:
            return {"error": "Not enough data"}
        return result
    except Exception as e:
        return {"error": str(e)}


# 💼 PORTFOLIO AI
@app.post("/portfolio")
def portfolio(tickers: list[str]):
    results = []

    for t in tickers:
        res = analyze_stock(t)
        if res:
            results.append(res)

    return {
        "portfolio": results
    }


# 🧠 AI RECOMMENDATION ENGINE

US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]
INDIA_STOCKS = ["INFY.NS", "TCS.NS", "HDFCBANK.NS", "RELIANCE.NS"]

@app.get("/recommendations")
def recommendations():
    candidates = US_STOCKS + INDIA_STOCKS

    results = []

    for t in candidates:
        res = analyze_stock(t)
        if res:
            results.append(res)

    # sort by best score
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return {
        "top_picks": results[:5]
    }
