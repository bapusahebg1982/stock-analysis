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


# ---------------- SAFE HELPERS ----------------

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


# ---------------- AI REASONING ----------------

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
            reasons.append("Oversold → rebound probability high")
        elif rsi_val > 70:
            reasons.append("Overbought → correction risk")

    if price and ma50:
        if price > ma50:
            reasons.append("Above MA50 → bullish momentum")
        else:
            reasons.append("Below MA50 → weak trend")

    if beaten:
        reasons.append("Near 1Y lows → potential value zone")

    return {
        "decision": decision,
        "reasoning": reasons,
        "timeframe": "3–9 months (BUY) / 1–3 months (HOLD/AVOID)",
        "risk": "High" if decision == "AVOID" else "Medium"
    }


# ---------------- NEWS ----------------

def get_news(stock):
    try:
        s = yf.Ticker(stock)
        news = s.news or []

        processed = []

        for n in news[:5]:
            title = n.get("title", "")

            score = 0
            if any(w in title.lower() for w in ["rise","surge","beat","strong"]):
                score += 1
            if any(w in title.lower() for w in ["fall","drop","weak","loss"]):
                score -= 1

            processed.append({
                "title": title,
                "sentiment": score
            })

        return processed
    except:
        return []


# ---------------- ALERTS ----------------

def get_alerts(stock):
    alerts = []

    t = stock["technicals"]

    if t["rsi"] and t["rsi"] < 30:
        alerts.append("RSI oversold → bounce setup")

    if t["trend"] == "Bullish":
        alerts.append("Bullish trend confirmed")

    if stock["beaten_down"]:
        alerts.append("Stock near yearly lows → value alert")

    return alerts


# ---------------- OPTIONS ----------------

def options_strategy(rsi_val):

    if rsi_val and rsi_val < 30:
        return {
            "strategy": "Bull Call Spread",
            "reason": "Oversold rebound setup",
            "risk": "Limited risk bullish trade"
        }

    if rsi_val and rsi_val > 70:
        return {
            "strategy": "Bear Put Spread",
            "reason": "Overbought reversal setup",
            "risk": "Hedged bearish trade"
        }

    return {
        "strategy": "Covered Call",
        "reason": "Neutral market conditions",
        "risk": "Income generation strategy"
    }


# ---------------- EVENTS ----------------

def get_events(stock):
    try:
        s = yf.Ticker(stock)
        cal = s.calendar

        if cal is not None and len(cal) > 0:
            return {
                "earnings": str(cal.index[0])
            }
    except:
        pass

    return {"earnings": "N/A"}


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

        r = safe(rsi(df).iloc[-1])
        ma50 = safe(df["Close"].rolling(50).mean().iloc[-1])

        info = {}
        try:
            info = s.get_info()
        except:
            pass

        sector = info.get("sector", "Unknown")
        market = "INDIA" if ".NS" in t else "US"

        score = 50

        if r and r < 30:
            score += 15
        elif r and r > 70:
            score -= 15

        if price and ma50 and price > ma50:
            score += 10

        beaten = (price / high) < 0.75 if high else False

        score = max(0, min(100, int(score)))

        tech = {
            "rsi": r,
            "ma50": ma50,
            "trend": "Bullish" if price > ma50 else "Bearish"
        }

        ai = ai_reasoning(price, r, ma50, beaten, score)

        return {
            "ticker": t,
            "price": price,
            "market": market,
            "sector": sector,
            "score": score,

            "technicals": tech,

            "fundamentals": {
                "pe": safe(info.get("trailingPE")),
                "profit_margin": safe(info.get("profitMargins")),
                "revenue_growth": safe(info.get("revenueGrowth"))
            },

            "high_low": {
                "1y_high": high
            },

            "beaten_down": beaten,

            "ai_view": ai,
            "news": get_news(t),
            "alerts": get_alerts({
                "technicals": tech,
                "beaten_down": beaten
            }),
            "options": options_strategy(r),
            "events": get_events(t)
        }

    except:
        return None


# ---------------- SIMPLE POOLS ----------------

US_POOL = ["AAPL","MSFT","GOOGL","NVDA","TSLA","AMZN","META","NFLX"]
INDIA_POOL = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS"]


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

        if r["sector"] == main["sector"] and r["score"] >= main["score"] - 10:
            sector_opps.append(r)

        if r["beaten_down"] and r["score"] >= 60:
            beaten_opps.append(r)

    return {
        "stock": main,
        "sector_opportunities": sector_opps,
        "beaten_down_opportunities": beaten_opps
    }
