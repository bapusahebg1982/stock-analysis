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


# ---------- HELPERS ----------

def safe_float(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return float(x)
    except:
        return None


def normalize_ticker(ticker):
    ticker = ticker.upper()
    try:
        test = yf.Ticker(ticker).history(period="5d")
        if test.empty and "." not in ticker:
            ticker += ".NS"
    except:
        pass
    return ticker


def compute_rsi(df, period=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# ---------- CORE ----------

def analyze_stock(raw):
    try:
        ticker = normalize_ticker(raw)
        stock = yf.Ticker(ticker)

        df_1y = stock.history(period="1y")
        df_5y = stock.history(period="5y")

        if df_1y.empty or len(df_1y) < 30:
            return None

        price = safe_float(df_1y["Close"].iloc[-1])

        # Technicals
        df_1y["RSI"] = compute_rsi(df_1y)
        rsi = safe_float(df_1y["RSI"].iloc[-1])

        ma50 = safe_float(df_1y["Close"].rolling(50).mean().iloc[-1])
        ma200 = safe_float(df_1y["Close"].rolling(200).mean().iloc[-1]) if len(df_1y) >= 200 else None

        # Volume
        avg_vol = safe_float(df_1y["Volume"].rolling(20).mean().iloc[-1])
        vol = safe_float(df_1y["Volume"].iloc[-1])
        volume_spike = False
        if avg_vol and vol:
            volume_spike = vol > 1.5 * avg_vol

        # Fundamentals (SAFE)
        try:
            info = stock.get_info()
        except:
            info = {}

        pe = safe_float(info.get("trailingPE"))
        profit_margin = safe_float(info.get("profitMargins"))
        revenue_growth = safe_float(info.get("revenueGrowth"))

        # High / Low
        high_1y = safe_float(df_1y["High"].max())
        low_1y = safe_float(df_1y["Low"].min())

        high_5y = safe_float(df_5y["High"].max()) if not df_5y.empty else None
        low_5y = safe_float(df_5y["Low"].min()) if not df_5y.empty else None

        # ---------- SCORING ----------
        score = 50
        reasons = []

        if rsi:
            if rsi < 30:
                score += 15
                reasons.append("Oversold (possible rebound)")
            elif rsi > 70:
                score -= 15
                reasons.append("Overbought (possible pullback)")

        if price and ma50 and price > ma50:
            score += 10
            reasons.append("Above 50-day average")

        if price and ma200 and price > ma200:
            score += 10
            reasons.append("Above 200-day average")

        if volume_spike:
            score += 5
            reasons.append("High trading volume")

        if profit_margin and profit_margin > 0.15:
            score += 5
            reasons.append("Strong profit margins")

        if revenue_growth and revenue_growth > 0:
            score += 5
            reasons.append("Growing revenue")

        score = max(0, min(100, int(score)))

        # Layman explanation
        if score >= 75:
            layman = "Strong stock with good momentum and fundamentals."
        elif score >= 60:
            layman = "Decent stock but not a strong buy yet."
        else:
            layman = "Weak signals. Better opportunities may exist."

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
            "reasons": reasons,
            "layman": layman
        }

    except Exception as e:
        return None


# ---------- MAIN ----------

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "NVDA", "TSLA",
    "RELIANCE.NS", "INFY.NS", "TCS.NS"
]

@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    main = analyze_stock(ticker)

    if not main:
        return {"error": "Ticker not found or insufficient data"}

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
