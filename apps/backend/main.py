import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.router import error_response, router
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

_queue_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _queue_task
    from case_queue.processor import queue_processor_loop
    _queue_task = asyncio.create_task(queue_processor_loop())
    logger.info("=== Queue processor background task started ===")
    yield
    if _queue_task:
        _queue_task.cancel()
        try:
            await _queue_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500, content=error_response("internal", "Something went wrong")
    )


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API is alive"}


app.include_router(router)
