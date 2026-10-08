from fastapi import APIRouter

from api.v1.endpoints import (
    anomalies,
    auth,
    case_queue,
    cases,
    clauses,
    dashboard,
    documents,
    firms,
    reference_documents,
)

router = APIRouter(prefix="/api/v1")


def error_response(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(auth.router)
router.include_router(firms.router)
router.include_router(cases.router)
router.include_router(documents.router)
router.include_router(reference_documents.router)
router.include_router(clauses.router)
router.include_router(anomalies.router)
router.include_router(dashboard.router)
router.include_router(case_queue.router)
