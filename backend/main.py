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


# ---------------- GPT-STYLE ANALYST ENGINE ----------------

def gpt_analyst(stock, price, rsi_val, ma50, beaten, fundamentals, sector):

    trend = "bullish" if ma50 and price > ma50 else "bearish"

    # -------- THESIS --------
    bull = []
    bear = []

    if rsi_val and rsi_val < 30:
        bull.append("Stock is oversold which historically leads to mean reversion rallies")
    if rsi_val and rsi_val > 70:
        bear.append("Overbought condition increases probability of short-term correction")

    if trend == "bullish":
        bull.append("Price is trading above trend support (MA50)")
    else:
        bear.append("Price is below key moving average indicating weakness")

    if beaten:
        bull.append("Stock is trading near yearly lows which may indicate value accumulation zone")

    if fundamentals.get("revenue_growth") and fundamentals["revenue_growth"] > 0.1:
        bull.append("Strong revenue growth supports long-term compounding story")

    if fundamentals.get("pe") and fundamentals["pe"] and fundamentals["pe"] > 50:
        bear.append("High valuation increases downside sensitivity")

    # -------- FINAL VIEW --------

    if len(bull) > len(bear) + 1:
        view = "BULLISH"
    elif len(bear) > len(bull):
        view = "BEARISH"
    else:
        view = "NEUTRAL"

    # -------- CASES --------

    return {
        "view": view,

        "bull_case": bull if bull else ["Limited bullish signals"],
        "bear_case": bear if bear else ["Limited bearish signals"],

        "short_term": "1–3 months volatility expected around earnings & momentum",
        "long_term": "6–12 months depends on earnings growth + sector trend",

        "risk_summary": (
            "High volatility stock" if rsi_val and (rsi_val > 70 or rsi_val < 30)
            else "Moderate risk profile"
        )
    }


# ---------------- TARGET ENGINE ----------------

def target_engine(price, rsi_val):

    if not price:
        return None

    if rsi_val and rsi_val < 30:
        return {
            "buy": round(price * 1.05, 2),
            "mid": round(price * 1.15, 2),
            "sell": round(price * 1.30, 2)
        }

    if rsi_val and rsi_val > 70:
        return {
            "buy": round(price * 0.95, 2),
            "mid": round(price * 0.90, 2),
            "sell": round(price * 0.85, 2)
        }

    return {
        "buy": round(price * 1.05, 2),
        "mid": round(price * 1.10, 2),
        "sell": round(price * 1.18, 2)
    }


# ---------------- ANALYSIS ----------------

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

        fundamentals = {
            "pe": safe(info.get("trailingPE")),
            "revenue_growth": safe(info.get("revenueGrowth"))
        }

        beaten = (price / high) < 0.75 if high else False

        gpt = gpt_analyst(t, price, r, ma50, beaten, fundamentals, sector)

        return {
            "ticker": t,
            "price": price,
            "market": market,
            "sector": sector,

            "technicals": {
                "rsi": r,
                "ma50": ma50,
                "trend": "Bullish" if price > ma50 else "Bearish"
            },

            "fundamentals": fundamentals,

            "beaten_down": beaten,

            "targets": target_engine(price, r),

            "gpt_analyst": gpt
        }

    except:
        return None


# ---------------- POOLS ----------------

US_POOL = ["AAPL","MSFT","GOOGL","NVDA","TSLA","AMZN","META"]
INDIA_POOL = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS"]


def get_pool(market):
    return US_POOL if market == "US" else INDIA_POOL


# ---------------- API ----------------

@app.get("/analyze/{ticker}")
def api(ticker: str):

    main = analyze_stock(ticker)
    if not main:
        return {"error": "Invalid ticker"}

    pool = get_pool(main["market"])

    return {
        "stock": main,
        "sector_opportunities": [],
        "beaten_down_opportunities": []
    }
