from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import math

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


# ---------------- HELPERS ----------------

def safe_float(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return round(float(x), 1)
    except:
        return None


def normalize_ticker(ticker: str):
    ticker = ticker.upper().strip()

    # Try US first, fallback India
    if "." not in ticker:
        test = yf.Ticker(ticker).history(period="5d")
        if test.empty:
            ticker = ticker + ".NS"

    return ticker


def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def is_beaten_down(price, high_1y):
    try:
        if not price or not high_1y:
            return False
        return (price / high_1y) < 0.7
    except:
        return False


# ---------------- CORE ANALYSIS ----------------

def analyze_stock(raw_ticker):
    try:
        ticker = normalize_ticker(raw_ticker)
        stock = yf.Ticker(ticker)

        df = stock.history(period="1y")
        df5 = stock.history(period="5y")

        if df.empty or len(df) < 50:
            return None

        price = safe_float(df["Close"].iloc[-1])

        # RSI
        df["RSI"] = compute_rsi(df)
        rsi = safe_float(df["RSI"].iloc[-1])

        ma50 = safe_float(df["Close"].rolling(50).mean().iloc[-1])
        ma200 = safe_float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

        # Volume
        avg_vol = safe_float(df["Volume"].rolling(20).mean().iloc[-1])
        vol = safe_float(df["Volume"].iloc[-1])
        volume_spike = bool(avg_vol and vol and vol > 1.5 * avg_vol)

        # Fundamentals (safe)
        try:
            info = stock.get_info()
        except:
            info = {}

        pe = safe_float(info.get("trailingPE"))
        profit_margin = safe_float(info.get("profitMargins"))
        revenue_growth = safe_float(info.get("revenueGrowth"))

        # High / Low
        high_1y = safe_float(df["High"].max())
        low_1y = safe_float(df["Low"].min())

        high_5y = safe_float(df5["High"].max()) if not df5.empty else None
        low_5y = safe_float(df5["Low"].min()) if not df5.empty else None

        # ---------------- SCORING ----------------

        score = 50
        reasons = []

        if rsi:
            if rsi < 30:
                score += 15
                reasons.append("Oversold (possible rebound)")
            elif rsi > 70:
                score -= 15
                reasons.append("Overbought (risk of pullback)")

        if price and ma50 and price > ma50:
            score += 10
            reasons.append("Above 50-day moving average")

        if price and ma200 and price > ma200:
            score += 10
            reasons.append("Strong long-term trend")

        if volume_spike:
            score += 5
            reasons.append("Unusual volume spike")

        if profit_margin and profit_margin > 0.15:
            score += 5
            reasons.append("Strong profit margins")

        if revenue_growth and revenue_growth > 0:
            score += 5
            reasons.append("Revenue growth positive")

        score = max(0, min(100, int(score)))

        # ---------------- LAYMAN INSIGHT ----------------

        if score >= 75:
            summary = "Strong stock with momentum and solid fundamentals."
        elif score >= 60:
            summary = "Mixed signals. Needs confirmation before entry."
        else:
            summary = "Weak momentum. Higher risk or better alternatives exist."

        return {
            "ticker": ticker,
            "price": price,
            "score": score,

            "fundamentals": {
                "pe": pe,
                "profit_margin": profit_margin,
                "revenue_growth": revenue_growth
            },

            "technicals": {
                "rsi": rsi,
                "ma50": ma50,
                "ma200": ma200,
                "volume_spike": volume_spike
            },

            "highs_lows": {
                "1y_high": high_1y,
                "1y_low": low_1y,
                "5y_high": high_5y,
                "5y_low": low_5y
            },

            "insights": {
                "summary": summary,
                "signals": reasons
            }
        }

    except:
        return None


# ---------------- UNIVERSE ----------------

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "NVDA", "TSLA",
    "RELIANCE.NS", "INFY.NS", "TCS.NS", "HDFCBANK.NS"
]


# ---------------- MAIN ANALYZE ----------------

@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    main = analyze_stock(ticker)

    if not main:
        return {"error": "Invalid or insufficient data"}

    better = []

    for t in UNIVERSE:
        if t != main["ticker"]:
            res = analyze_stock(t)
            if res:
                beat = is_beaten_down(res["price"], res["highs_lows"]["1y_high"])

                if res["score"] >= 65 or beat:
                    res["is_beaten_down"] = beat
                    better.append(res)

    better = sorted(better, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "stock": main,
        "better_options": better
    }


# ---------------- OPPORTUNITIES (FILTERED) ----------------

@app.get("/opportunities")
def opportunities(max_price: float = 1000):
    results = []

    for t in UNIVERSE:
        res = analyze_stock(t)
        if res and res["price"] and res["price"] <= max_price:
            beat = is_beaten_down(res["price"], res["highs_lows"]["1y_high"])

            if res["score"] >= 65 or beat:
                res["is_beaten_down"] = beat
                results.append(res)

    return {
        "opportunities": sorted(results, key=lambda x: x["score"], reverse=True)
    }
