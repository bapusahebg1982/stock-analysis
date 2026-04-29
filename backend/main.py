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


# ---------------- UTIL ----------------

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


# ---------------- AI REASONING ENGINE ----------------

def ai_reasoning(price, rsi_val, ma50, beaten, score):

    if score >= 75:
        decision = "BUY"
    elif score >= 60:
        decision = "HOLD"
    else:
        decision = "AVOID"

    reasons = []

    if rsi_val is not None:
        if rsi_val < 30:
            reasons.append("Oversold condition → rebound potential")
        elif rsi_val > 70:
            reasons.append("Overbought → short-term risk")

    if price and ma50:
        if price > ma50:
            reasons.append("Above trend → bullish momentum")
        else:
            reasons.append("Below trend → weak momentum")

    if beaten:
        reasons.append("Trading near yearly lows → value zone")

    timeframe = (
        "3–9 months upside" if decision == "BUY"
        else "1–3 months consolidation" if decision == "HOLD"
        else "No strong setup"
    )

    return {
        "decision": decision,
        "reasoning": reasons,
        "timeframe": timeframe,
        "risk": "High" if decision == "AVOID" else "Medium"
    }


# ---------------- CORE ANALYSIS ----------------

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
        market = "INDIA" if ".NS" in t else "US"

        # ---------------- SCORE ----------------
        score = 50

        if r and r < 30:
            score += 15
        elif r and r > 70:
            score -= 15

        if price and ma50 and price > ma50:
            score += 10

        beaten = (price / high) < 0.75 if high else False

        score = max(0, min(100, int(score)))

        # ---------------- AI VIEW ----------------
        ai_view = ai_reasoning(price, r, ma50, beaten, score)

        return {
            "ticker": t,
            "price": price,
            "market": market,
            "sector": sector,
            "score": score,

            "fundamentals": {
                "pe": safe(info.get("trailingPE")),
                "profit_margin": safe(info.get("profitMargins")),
                "revenue_growth": safe(info.get("revenueGrowth"))
            },

            "technicals": {
                "rsi": r,
                "ma50": ma50,
                "ma200": ma200,
                "trend": "Bullish" if price > ma50 else "Bearish"
            },

            "high_low": {
                "1y_high": high,
                "1y_low": low
            },

            "signals": ai_view["reasoning"],
            "ai_view": ai_view,
            "beaten_down": beaten
        }

    except:
        return None


# ---------------- SIMPLE MARKET POOLS ----------------

US_POOL = ["AAPL","MSFT","GOOGL","NVDA","TSLA","AMZN","META","NFLX","AMD","INTC"]
INDIA_POOL = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","LT.NS"]


def get_pool(market):
    return US_POOL if market == "US" else INDIA_POOL


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    pool = get_pool(main["market"])

    sector_opps = []
    beaten_opps = []

    for p in pool:
        if p == main["ticker"]:
            continue

        r = analyze_stock(p)
        if not r:
            continue

        if r["market"] != main["market"]:
            continue

        # sector logic
        if r["sector"] == main["sector"] and r["score"] >= main["score"] - 10:
            sector_opps.append(r)

        # beaten logic
        if r["beaten_down"] and r["score"] >= 60:
            beaten_opps.append(r)

    return {
        "stock": main,
        "sector_opportunities": sector_opps[:5],
        "beaten_down_opportunities": beaten_opps[:5]
    }
