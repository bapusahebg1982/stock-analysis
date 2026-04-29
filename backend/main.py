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


# Core scoring logic
def analyze_stock(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")

    if df.empty or len(df) < 50:
        return None

    price = float(df["Close"].iloc[-1])

    df["RSI"] = compute_rsi(df)
    rsi = float(df["RSI"].iloc[-1])

    ma50 = float(df["Close"].rolling(50).mean().iloc[-1])

    ma200 = None
    if len(df) >= 200:
        ma200 = float(df["Close"].rolling(200).mean().iloc[-1])

    score = 50

    if rsi < 30:
        score += 20
    elif rsi > 70:
        score -= 20

    if price > ma50:
        score += 10
    if ma200 and price > ma200:
        score += 10

    score = max(0, min(100, int(score)))

    return {
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "score": score
    }


# Sector mapping (starter)
SECTOR_MAP = {
    "AAPL": ["MSFT", "GOOGL", "NVDA"],
    "MSFT": ["AAPL", "GOOGL", "NVDA"],
    "GOOGL": ["AAPL", "MSFT", "META"],
    "TSLA": ["NIO", "RIVN", "F"],
    "INFY.NS": ["TCS.NS", "WIPRO.NS", "HCLTECH.NS"]
}


@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    try:
        main = analyze_stock(ticker)

        if not main:
            return {"error": "Not enough data"}

        peers = SECTOR_MAP.get(ticker.upper(), [])

        peer_results = []
        for p in peers:
            res = analyze_stock(p)
            if res:
                peer_results.append(res)

        # Sort best first
        peer_results = sorted(peer_results, key=lambda x: x["score"], reverse=True)

        return {
            "ticker": main["ticker"],
            "price": main["price"],
            "scores": {"total": main["score"]},
            "peers": peer_results
        }

    except Exception as e:
        return {"error": str(e)}
