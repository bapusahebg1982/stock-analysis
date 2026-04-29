from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ ADD THIS BLOCK
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import yfinance as yf
import pandas as pd

def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    stock = yf.Ticker(ticker)
    df = stock.history(period="6mo")

    if df.empty:
        return {"error": "Invalid ticker"}

    price = float(df["Close"].iloc[-1])

    # Indicators
    df["RSI"] = compute_rsi(df)
    rsi = float(df["RSI"].iloc[-1])

    ma50 = df["Close"].rolling(50).mean().iloc[-1]
    ma200 = df["Close"].rolling(200).mean().iloc[-1]

    score = 50

    # RSI scoring
    if rsi < 30:
        score += 20
    elif rsi > 70:
        score -= 20

    # Trend scoring
    if price > ma50:
        score += 10
    if price > ma200:
        score += 10

    score = max(0, min(100, int(score)))

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "scores": {"total": score},
        "technicals": {
            "rsi": round(rsi, 2),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2)
        }
    }
