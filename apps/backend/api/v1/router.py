from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


def error_response(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
