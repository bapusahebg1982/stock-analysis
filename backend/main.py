from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ ADD THIS BLOCK
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import yfinance as yf

@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1d")

    price = float(hist["Close"].iloc[-1]) if not hist.empty else 0

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "scores": {"total": 75}
    }
