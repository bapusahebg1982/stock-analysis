from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- HELPERS ----------------

def safe(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return round(float(x), 2)
    except:
        return None


def normalize(t):
    t = t.upper().strip()
    if "." not in t:
        if yf.Ticker(t).history(period="5d").empty:
            t += ".NS"
    return t


def rsi(df):
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# ---------------- CORE ENGINE ----------------

def analyze_stock(raw):
    try:
        t = normalize(raw)
        s = yf.Ticker(t)

        df = s.history(period="1y")
        if df.empty:
            return None

        price = safe(df["Close"].iloc[-1])
        high = safe(df["High"].max())
        low = safe(df["Low"].min())

        r = safe(rsi(df).iloc[-1])
        ma50 = safe(df["Close"].rolling(50).mean().iloc[-1])
        ma200 = safe(df["Close"].rolling(200).mean().iloc[-1])

        info = {}
        try:
            info = s.get_info()
        except:
            pass

        sector = info.get("sector", "Unknown")

        # ---------------- FUNDAMENTALS ----------------
        fundamentals = {
            "pe": safe(info.get("trailingPE")),
            "profit_margin": safe(info.get("profitMargins")),
            "revenue_growth": safe(info.get("revenueGrowth"))
        }

        # ---------------- TECHNICALS ----------------
        trend = "Neutral"
        if price and ma50:
            if price > ma50:
                trend = "Bullish"
            else:
                trend = "Bearish"

        technicals = {
            "rsi": r,
            "ma50": ma50,
            "ma200": ma200,
            "trend": trend
        }

        # ---------------- SCORE ----------------
        score = 50
        reasons = []

        if r and r < 30:
            score += 15
            reasons.append("Oversold")
        elif r and r > 70:
            score -= 15
            reasons.append("Overbought")

        if trend == "Bullish":
            score += 10
            reasons.append("Uptrend confirmed")

        score = max(0, min(100, int(score)))

        beaten = (price / high) < 0.75 if high else False

        # ---------------- INVESTMENT VIEW ----------------

        short_target = round(price * 1.08, 2)
        long_target = round(price * 1.25, 2)

        short_view = {
            "horizon": "1–3 months",
            "target": short_target,
            "thesis": "Momentum + technical continuation expected",
            "risk": "Medium"
        }

        long_view = {
            "horizon": "6–12 months",
            "target": long_target,
            "thesis": "Fundamental recovery + sector growth",
            "risk": "Medium-Low"
        }

        return {
            "ticker": t,
            "price": price,
            "sector": sector,
            "score": score,

            "fundamentals": fundamentals,
            "technicals": technicals,

            "high_low": {
                "1y_high": high,
                "1y_low": low
            },

            "signals": reasons,

            "investment_view": {
                "short_term": short_view,
                "long_term": long_view
            },

            "beaten_down": beaten
        }

    except:
        return None


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    market_universe = [
        "AAPL","MSFT","GOOGL","NVDA","TSLA",
        "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS"
    ]

    sector_opps = []
    beaten_opps = []

    for u in market_universe:
        if u == main["ticker"]:
            continue

        r = analyze_stock(u)
        if not r:
            continue

        # same sector logic
        if r["sector"] == main["sector"] and r["score"] >= main["score"] - 10:
            sector_opps.append(r)

        # beaten down logic (same market implied via suffix)
        if r["beaten_down"] and r["score"] >= 60:
            beaten_opps.append(r)

    sector_opps = sorted(sector_opps, key=lambda x: x["score"], reverse=True)[:5]
    beaten_opps = sorted(beaten_opps, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "stock": main,
        "sector_opportunities": sector_opps,
        "beaten_down_opportunities": beaten_opps
    }
