from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.v1.router import error_response, router
from core.config import settings

app = FastAPI()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500, content=error_response("internal", "Something went wrong")
    )


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API is alive"}


app.include_router(router)
