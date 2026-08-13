from fastapi import FastAPI

from core.config import settings

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": f"{settings.app_name} API is alive"}

@app.get("/health")
def health():
    return{"status": "ok"}
