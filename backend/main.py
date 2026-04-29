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

@app.get("/")
def root():
    return {"status": "Backend running"}


# ---------- UTIL ----------
def safe(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return float(round(x, 2))
    except:
        return None


def normalize(t):
    t = t.upper()
    if "." not in t:
        if yf.Ticker(t).history(period="5d").empty:
            t += ".NS"
    return t


def rsi(df, period=14):
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# ---------- CORE ANALYSIS ----------
def analyze(ticker):
    try:
        t = normalize(ticker)
        s = yf.Ticker(t)

        df = s.history(period="1y")
        df5 = s.history(period="5y")

        if df.empty:
            return None

        price = safe(df["Close"].iloc[-1])
        high_1y = safe(df["High"].max())
        low_1y = safe(df["Low"].min())

        r = safe(rsi(df).iloc[-1])
        ma50 = safe(df["Close"].rolling(50).mean().iloc[-1])

        info = {}
        try:
            info = s.get_info()
        except:
            pass

        sector = info.get("sector", "Unknown")

        pe = safe(info.get("trailingPE"))
        profit = safe(info.get("profitMargins"))
        revenue = safe(info.get("revenueGrowth"))

        score = 50
        reasons = []

        if r and r < 30:
            score += 15
            reasons.append("Oversold condition")
        elif r and r > 70:
            score -= 15
            reasons.append("Overbought condition")

        if price and ma50 and price > ma50:
            score += 10
            reasons.append("Above trend (MA50)")

        if profit and profit > 0.15:
            score += 5
            reasons.append("Strong profitability")

        if revenue and revenue > 0:
            score += 5
            reasons.append("Revenue growing")

        score = max(0, min(100, int(score)))

        beaten = (price / high_1y) < 0.7 if high_1y else False

        # Simple target logic
        target_1 = round(price * 1.1, 2)
        target_2 = round(price * 1.25, 2)

        return {
            "ticker": t,
            "price": price,
            "score": score,
            "sector": sector,
            "fundamentals": {
                "pe": pe,
                "profit_margin": profit,
                "revenue_growth": revenue
            },
            "technicals": {
                "rsi": safe(r),
                "ma50": ma50
            },
            "highs_lows": {
                "1y_high": high_1y,
                "1y_low": low_1y
            },
            "insights": reasons,
            "beaten_down": beaten,
            "targets": {
                "short": target_1,
                "mid": target_2,
                "timeframe": "3-9 months"
            }
        }

    except:
        return None


# ---------- MAIN ----------
@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):
    main = analyze(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    universe = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "RELIANCE.NS", "INFY.NS", "TCS.NS"]

    same_sector = []
    beaten_down = []

    for u in universe:
        if u != main["ticker"]:
            r = analyze(u)
            if not r:
                continue

            # Sector filter
            if r["sector"] == main["sector"] and r["score"] >= main["score"] - 5:
                same_sector.append(r)

            # Beaten down strong stocks
            if r["beaten_down"] and r["score"] >= 65:
                beaten_down.append(r)

    same_sector = sorted(same_sector, key=lambda x: x["score"], reverse=True)[:5]
    beaten_down = sorted(beaten_down, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "stock": main,
        "sector_opportunities": same_sector,
        "beaten_down_opportunities": beaten_down
    }
