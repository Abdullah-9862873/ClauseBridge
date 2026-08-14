from fastapi import FastAPI

from core.config import settings

app = FastAPI()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API is alive"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
