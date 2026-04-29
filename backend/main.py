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
        high_1y = safe(df["High"].max())

        r = safe(rsi(df).iloc[-1])
        ma50 = safe(df["Close"].rolling(50).mean().iloc[-1])

        info = {}
        try:
            info = s.get_info()
        except:
            pass

        sector = info.get("sector", "Unknown")
        market = detect_market(t)

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

        beaten = (price / high_1y) < 0.75 if high_1y else False

        return {
            "ticker": t,
            "price": price,
            "score": score,
            "sector": sector,
            "market": market,
            "beaten_down": beaten,
            "signals": signals
        }

    except:
        return None


# ---------------- PEER DISCOVERY (KEY FIX) ----------------

def get_dynamic_peers(sector, market, exclude):

    # Instead of universe → we scan index-like candidates
    if market == "US":
        candidates = [
            "AAPL","MSFT","GOOGL","NVDA","AMZN","META","TSLA","NFLX","INTC","AMD","ORCL"
        ]
    else:
        candidates = [
            "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
            "SBIN.NS","LT.NS","WIPRO.NS"
        ]

    results = []

    for c in candidates:
        if c == exclude:
            continue

        r = analyze_stock(c)
        if not r:
            continue

        # ONLY SAME MARKET
        if r["market"] != market:
            continue

        # sector similarity (soft match, not strict)
        if r["sector"] == sector:
            results.append(r)

    return sorted(results, key=lambda x: x["score"], reverse=True)[:8]


# ---------------- BEATEN DOWN SCREENER ----------------

def get_beaten_down(market):

    if market == "US":
        candidates = [
            "AAPL","MSFT","GOOGL","NVDA","TSLA","META","AMD","INTC"
        ]
    else:
        candidates = [
            "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
            "SBIN.NS","LT.NS"
        ]

    results = []

    for c in candidates:
        r = analyze_stock(c)
        if not r:
            continue

        if r["market"] != market:
            continue

        if r["beaten_down"] and r["score"] >= 60:
            results.append(r)

    return sorted(results, key=lambda x: x["score"], reverse=True)[:8]


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def analyze_api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    sector_opps = get_dynamic_peers(
        main["sector"],
        main["market"],
        main["ticker"]
    )

    beaten_opps = get_beaten_down(main["market"])

    return {
        "stock": main,
        "sector_opportunities": sector_opps,
        "beaten_down_opportunities": beaten_opps
    }
