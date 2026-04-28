from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "AI Stock Backend Running"}

@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    return {
        "ticker": ticker,
        "price": 100,
        "scores": {
            "total": 75
        }
    }