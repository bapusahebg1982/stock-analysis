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


# ---------------- TARGET ENGINE ----------------

def target_engine(price, rsi_val):

    if not price:
        return None

    if rsi_val and rsi_val < 30:
        return {
            "buy_target": round(price * 1.05, 2),
            "mid_target": round(price * 1.15, 2),
            "sell_target": round(price * 1.30, 2)
        }

    if rsi_val and rsi_val > 70:
        return {
            "buy_target": round(price * 0.95, 2),
            "mid_target": round(price * 0.90, 2),
            "sell_target": round(price * 0.85, 2)
        }

    return {
        "buy_target": round(price * 1.05, 2),
        "mid_target": round(price * 1.10, 2),
        "sell_target": round(price * 1.18, 2)
    }


# ---------------- AI ENGINE ----------------

def ai_engine(price, rsi_val, ma50, beaten, score):

    if score >= 75:
        decision = "BUY"
    elif score >= 60:
        decision = "HOLD"
    else:
        decision = "AVOID"

    reasons = []

    if rsi_val:
        if rsi_val < 30:
            reasons.append("Oversold → rebound probability high")
        elif rsi_val > 70:
            reasons.append("Overbought → correction risk")

    if price and ma50:
        if price > ma50:
            reasons.append("Above MA50 → bullish trend")
        else:
            reasons.append("Below MA50 → weak trend")

    if beaten:
        reasons.append("Near 1Y low → value zone")

    return {
        "decision": decision,
        "reasoning": reasons,
        "timeframe": "3–9 months",
        "risk": "High" if decision == "AVOID" else "Medium"
    }


# ---------------- NEWS ----------------

def news_engine(stock):
    try:
        s = yf.Ticker(stock)
        news = s.news or []

        out = []

        for n in news[:5]:
            title = n.get("title", "")

            sentiment = 0
            if any(w in title.lower() for w in ["rise","surge","beat","strong"]):
                sentiment += 1
            if any(w in title.lower() for w in ["fall","drop","weak","loss"]):
                sentiment -= 1

            out.append({
                "title": title,
                "sentiment": sentiment
            })

        return out
    except:
        return []


# ---------------- ALERTS ----------------

def alerts_engine(stock):

    alerts = []
    t = stock["technicals"]

    if t["rsi"] and t["rsi"] < 30:
        alerts.append("RSI oversold → bounce setup")

    if t["trend"] == "Bullish":
        alerts.append("Bullish momentum confirmed")

    if stock["beaten_down"]:
        alerts.append("Stock near yearly low → value opportunity")

    return alerts


# ---------------- OPTIONS ----------------

def options_engine(rsi_val):

    if rsi_val and rsi_val < 30:
        return {
            "strategy": "Bull Call Spread",
            "reason": "Rebound expected",
            "risk": "Limited risk bullish setup"
        }

    if rsi_val and rsi_val > 70:
        return {
            "strategy": "Bear Put Spread",
            "reason": "Correction expected",
            "risk": "Hedged bearish setup"
        }

    return {
        "strategy": "Covered Call",
        "reason": "Neutral market",
        "risk": "Income strategy"
    }


# ---------------- EVENTS ----------------

def events_engine(stock):
    try:
        s = yf.Ticker(stock)
        cal = s.calendar

        if cal is not None and len(cal) > 0:
            return {"earnings": str(cal.index[0])}
    except:
        pass

    return {"earnings": "N/A"}


# ---------------- ANALYZE ----------------

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
                "1y_high": high,
                "1y_low": low
            },

            "beaten_down": beaten,

            "ai_view": ai_engine(price, r, ma50, beaten, score),
            "targets": target_engine(price, r),
            "news": news_engine(t),
            "alerts": alerts_engine({
                "technicals": tech,
                "beaten_down": beaten
            }),
            "options": options_engine(r),
            "events": events_engine(t)
        }

    except:
        return None


# ---------------- POOLS ----------------

US_POOL = ["AAPL","MSFT","GOOGL","NVDA","TSLA","AMZN","META","NFLX"]
INDIA_POOL = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS"]


def get_pool(market):
    return US_POOL if market == "US" else INDIA_POOL


# ---------------- BEATEN DOWN ENGINE ----------------

def beaten_engine(main, pool):

    results = []

    for p in pool:
        if p == main["ticker"]:
            continue

        r = analyze_stock(p)
        if not r:
            continue

        if r["market"] != main["market"]:
            continue

        if r["price"] and r["high_low"]["1y_high"]:
            drop = r["price"] / r["high_low"]["1y_high"]

            if drop < 0.7 and r["score"] >= 60:
                r["drop_pct"] = round((1 - drop) * 100, 2)
                results.append(r)

    return sorted(results, key=lambda x: x["drop_pct"], reverse=True)


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    pool = get_pool(main["market"])

    sector = []
    beaten = beaten_engine(main, pool)

    for p in pool:
        if p == main["ticker"]:
            continue

        r = analyze_stock(p)
        if not r:
            continue

        if r["market"] == main["market"] and r["sector"] == main["sector"]:
            sector.append(r)

    return {
        "stock": main,
        "sector_opportunities": sector,
        "beaten_down_opportunities": beaten
    }
