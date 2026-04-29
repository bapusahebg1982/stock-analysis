from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd

app = FastAPI()

# ✅ CORS (required for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ ROOT ROUTE (THIS FIXES YOUR ERROR)
@app.get("/")
def root():
    return {"status": "Backend running"}

# RSI calculation
def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Main API
@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")

        if df.empty or len(df) < 50:
            return {"error": "Not enough data"}

        price = float(df["Close"].iloc[-1])

        # Indicators
        df["RSI"] = compute_rsi(df)
        rsi = float(df["RSI"].iloc[-1])

        ma50 = float(df["Close"].rolling(50).mean().iloc[-1])
        ma200 = float(df["Close"].rolling(200).mean().iloc[-1])

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
            "ticker": ticker.upper(),
            "price": round(price, 2),
            "scores": {"total": score},
            "technicals": {
                "rsi": round(rsi, 2),
                "ma50": round(ma50, 2),
                "ma200": round(ma200, 2)
            }
        }

    except Exception as e:
        return {"error": str(e)}
