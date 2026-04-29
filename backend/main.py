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


# Normalize ticker
def normalize_ticker(ticker):
    ticker = ticker.upper()
    if "." not in ticker:
        test = yf.Ticker(ticker).history(period="5d")
        if test.empty:
            ticker += ".NS"
    return ticker


# RSI
def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# Core analysis
def analyze_stock(raw):
    ticker = normalize_ticker(raw)
    stock = yf.Ticker(ticker)

    df_1y = stock.history(period="1y")
    df_5y = stock.history(period="5y")

    if df_1y.empty:
        return None

    price = float(df_1y["Close"].iloc[-1])

    # Technicals
    df_1y["RSI"] = compute_rsi(df_1y)
    rsi = float(df_1y["RSI"].iloc[-1])

    ma50 = df_1y["Close"].rolling(50).mean().iloc[-1]
    ma200 = df_1y["Close"].rolling(200).mean().iloc[-1]

    # Volume spike
    avg_vol = df_1y["Volume"].rolling(20).mean().iloc[-1]
    vol = df_1y["Volume"].iloc[-1]
    volume_spike = vol > 1.5 * avg_vol

    # Fundamentals
    info = stock.info

    pe = info.get("trailingPE")
    profit_margin = info.get("profitMargins")
    revenue_growth = info.get("revenueGrowth")

    # High / Low
    high_1y = df_1y["High"].max()
    low_1y = df_1y["Low"].min()

    high_5y = df_5y["High"].max() if not df_5y.empty else None
    low_5y = df_5y["Low"].min() if not df_5y.empty else None

    # Score
    score = 50
    reasons = []

    if rsi < 30:
        score += 15
        reasons.append("Stock is oversold (possible rebound)")
    elif rsi > 70:
        score -= 15
        reasons.append("Stock is overbought (possible pullback)")

    if price > ma50:
        score += 10
        reasons.append("Short-term trend is bullish")

    if price > ma200:
        score += 10
        reasons.append("Long-term trend is strong")

    if volume_spike:
        score += 5
        reasons.append("High trading volume (strong interest)")

    if profit_margin and profit_margin > 0.15:
        score += 5
        reasons.append("Healthy profit margins")

    if revenue_growth and revenue_growth > 0:
        score += 5
        reasons.append("Company is growing revenue")

    score = max(0, min(100, int(score)))

    # Layman explanation
    layman = "This stock shows "
    if score > 75:
        layman += "strong overall performance with good growth and momentum."
    elif score > 60:
        layman += "moderate strength but needs confirmation before investing."
    else:
        layman += "weak signals and may underperform in near term."

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "score": score,
        "fundamentals": {
            "pe": pe,
            "profit_margin": profit_margin,
            "revenue_growth": revenue_growth
        },
        "technicals": {
            "rsi": round(rsi, 2),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "volume_spike": volume_spike
        },
        "highs_lows": {
            "1y_high": round(high_1y, 2),
            "1y_low": round(low_1y, 2),
            "5y_high": round(high_5y, 2) if high_5y else None,
            "5y_low": round(low_5y, 2) if low_5y else None
        },
        "reasons": reasons,
        "layman": layman
    }


# Better alternatives
UNIVERSE = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "RELIANCE.NS", "INFY.NS"]

@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    better = []

    for t in UNIVERSE:
        if t != main["ticker"]:
            res = analyze_stock(t)
            if res and res["score"] > main["score"]:
                better.append(res)

    better = sorted(better, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "stock": main,
        "better_options": better
    }
