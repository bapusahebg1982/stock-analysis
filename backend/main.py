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


# Backtest RSI strategy
def backtest_rsi(df):
    df = df.copy()
    df["RSI"] = compute_rsi(df)

    position = 0
    entry_price = 0
    trades = []
    capital = 10000

    for i in range(1, len(df)):
        rsi = df["RSI"].iloc[i]
        price = df["Close"].iloc[i]

        # BUY
        if rsi < 30 and position == 0:
            position = 1
            entry_price = price

        # SELL
        elif rsi > 70 and position == 1:
            profit = (price - entry_price) / entry_price
            trades.append(profit)
            capital *= (1 + profit)
            position = 0

    total_return = (capital - 10000) / 10000 * 100
    win_rate = (
        len([t for t in trades if t > 0]) / len(trades) * 100
        if trades else 0
    )

    return {
        "return_pct": round(total_return, 2),
        "trades": len(trades),
        "win_rate": round(win_rate, 2)
    }


# Analyze + Backtest
@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")

        if df.empty or len(df) < 50:
            return {"error": "Not enough data"}

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

        # BACKTEST
        backtest = backtest_rsi(df)

        return {
            "ticker": ticker.upper(),
            "price": round(price, 2),
            "scores": {"total": score},
            "backtest": backtest
        }

    except Exception as e:
        return {"error": str(e)}
