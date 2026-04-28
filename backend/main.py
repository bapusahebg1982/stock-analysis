from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    return {
        "ticker": ticker,
        "price": 100,
        "scores": {"total": 75}
    }
