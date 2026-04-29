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

# ---------------- MARKET SEPARATION ----------------

US_UNIVERSE = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]

INDIA_UNIVERSE = ["RELIANCE.NS", "INFY.NS", "TCS.NS", "HDFCBANK.NS"]


def detect_market(ticker: str):
    if ".NS" in ticker:
        return "INDIA"
    return "US"


def normalize(t):
    t = t.upper().strip()
    if "." not in t:
        # try US first
        test = yf.Ticker(t).history(period="5d")
        if test.empty:
            t += ".NS"
    return t


def safe(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return round(float(x), 2)
    except:
        return None


def rsi(df):
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# ---------------- CORE ANALYSIS ----------------

def analyze_stock(raw):
    try:
        t = normalize(raw)
        s = yf.Ticker(t)

        df = s.history(period="1y")
        df5 = s.history(period="5y")

        if df.empty:
            return None

        price = safe(df["Close"].iloc[-1])

        r = safe(rsi(df).iloc[-1])
        ma50 = safe(df["Close"].rolling(50).mean().iloc[-1])

        high_1y = safe(df["High"].max())
        low_1y = safe(df["Low"].min())

        info = {}
        try:
            info = s.get_info()
        except:
            pass

        sector = info.get("sector", "Unknown")
        market = detect_market(t)

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
            reasons.append("Above trend")

        beaten = (price / high_1y) < 0.7 if high_1y else False

        return {
            "ticker": t,
            "price": price,
            "score": score,
            "sector": sector,
            "market": market,
            "technicals": {
                "rsi": r,
                "ma50": ma50
            },
            "high_1y": high_1y,
            "low_1y": low_1y,
            "beaten_down": beaten,
            "signals": reasons
        }

    except:
        return None


# ---------------- MAIN API ----------------

@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    market = main["market"]
    sector = main["sector"]

    universe = US_UNIVERSE if market == "US" else INDIA_UNIVERSE

    sector_opps = []
    beaten_opps = []

    for u in universe:
        r = analyze_stock(u)
        if not r:
            continue

        # SAME MARKET FIX (CRITICAL)
        if r["market"] != market:
            continue

        # SAME SECTOR OPPORTUNITIES
        if r["sector"] == sector and r["score"] >= main["score"] - 5:
            sector_opps.append(r)

        # BEATEN DOWN (ALL SECTORS SAME MARKET)
        if r["beaten_down"] and r["score"] >= 65:
            beaten_opps.append(r)

    sector_opps = sorted(sector_opps, key=lambda x: x["score"], reverse=True)[:5]
    beaten_opps = sorted(beaten_opps, key=lambda x: x["score"], reverse=True)[:5]

    return {
        "stock": main,
        "sector_opportunities": sector_opps,
        "beaten_down_opportunities": beaten_opps
    }
