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

# ---------------- CLEAN MARKET SEGREGATION ----------------

US_POOL = [
    "AAPL","MSFT","GOOGL","NVDA","TSLA","AMZN","META","NFLX","AMD","INTC"
]

INDIA_POOL = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","LT.NS","WIPRO.NS","BAJFINANCE.NS"
]


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


def detect_market(t):
    return "INDIA" if ".NS" in t else "US"


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

        market = detect_market(t)
        sector = info.get("sector", "Unknown")

        score = 50
        signals = []

        if r and r < 30:
            score += 15
            signals.append("Oversold")
        elif r and r > 70:
            score -= 15
            signals.append("Overbought")

        if price and ma50 and price > ma50:
            score += 10
            signals.append("Uptrend")

        beaten = (price / high) < 0.75 if high else False

        return {
            "ticker": t,
            "price": price,
            "score": score,
            "market": market,
            "sector": sector,
            "beaten_down": beaten,
            "signals": signals
        }

    except:
        return None


# ---------------- MARKET FILTER ENGINE ----------------

def get_pool(market):
    return US_POOL if market == "US" else INDIA_POOL


def get_sector_opps(main, pool):
    results = []

    for t in pool:
        if t == main["ticker"]:
            continue

        r = analyze_stock(t)
        if not r:
            continue

        # STRICT MARKET ENFORCEMENT
        if r["market"] != main["market"]:
            continue

        # SOFT SECTOR MATCH (NOT STRICT STRING DEPENDENCY)
        if r["score"] >= main["score"] - 10:
            results.append(r)

    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]


def get_beaten_down(main):
    pool = get_pool(main["market"])

    results = []

    for t in pool:
        if t == main["ticker"]:
            continue

        r = analyze_stock(t)
        if not r:
            continue

        if r["market"] != main["market"]:
            continue

        if r["beaten_down"] and r["score"] >= 60:
            results.append(r)

    return sorted(results, key=lambda x: x["score"], reverse=True)[:5]


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    pool = get_pool(main["market"])

    return {
        "stock": main,
        "sector_opportunities": get_sector_opps(main, pool),
        "beaten_down_opportunities": get_beaten_down(main)
    }
