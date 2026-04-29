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


# ---------------- ANALYSIS ----------------

def analyze_stock(raw):
    try:
        t = normalize(raw)
        s = yf.Ticker(t)

        df = s.history(period="1y")

        if df.empty:
            return None

        price = safe(df["Close"].iloc[-1])
        high_1y = safe(df["High"].max())

        r = safe(rsi(df).iloc[-1])
        ma50 = safe(df["Close"].rolling(50).mean().iloc[-1])

        info = {}
        try:
            info = s.get_info()
        except:
            pass

        sector = info.get("sector", "Unknown")

        score = 50
        reasons = []

        if r and r < 30:
            score += 15
            reasons.append("Oversold")
        elif r and r > 70:
            score -= 15
            reasons.append("Overbought")

        if price and ma50 and price > ma50:
            score += 10
            reasons.append("Uptrend")

        # Beaten down (IMPORTANT FIX)
        beaten = False
        if price and high_1y:
            beaten = (price / high_1y) < 0.75  # relaxed threshold

        score = max(0, min(100, int(score)))

        return {
            "ticker": t,
            "price": price,
            "score": score,
            "sector": sector,
            "beaten_down": beaten,
            "signals": reasons
        }

    except:
        return None


# ---------------- UNIVERSAL LIST ----------------

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "NVDA", "TSLA",
    "RELIANCE.NS", "INFY.NS", "TCS.NS", "HDFCBANK.NS"
]


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    sector_opps = []
    beaten_opps = []

    for u in UNIVERSE:
        if u == main["ticker"]:
            continue  # 🔥 CRITICAL FIX (no self recommendation)

        r = analyze_stock(u)
        if not r:
            continue

        # SAME SECTOR LOGIC (FIXED)
        if r["sector"] == main["sector"]:
            if r["score"] >= main["score"] - 10:
                sector_opps.append(r)

        # BEATEN DOWN (NO SECTOR LIMIT)
        if r["beaten_down"] and r["score"] >= 55:
            beaten_opps.append(r)

    # Sorting
    sector_opps = sorted(sector_opps, key=lambda x: x["score"], reverse=True)[:5]
    beaten_opps = sorted(beaten_opps, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "stock": main,
        "sector_opportunities": sector_opps,
        "beaten_down_opportunities": beaten_opps
    }
