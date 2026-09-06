from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from db.session import get_session
from models import Anomaly, Case, Clause, Document, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int]:
    firm_id = user.firm_id

    case_count = await session.scalar(
        select(func.count()).select_from(Case).where(Case.firm_id == firm_id)
    )

    doc_count = await session.scalar(
        select(func.count())
        .select_from(Document)
        .join(Case, Case.id == Document.case_id)
        .where(Case.firm_id == firm_id)
    )

    anomaly_count = await session.scalar(
        select(func.count())
        .select_from(Anomaly)
        .join(Clause, Clause.id == Anomaly.clause_id)
        .join(Document, Document.id == Clause.document_id)
        .join(Case, Case.id == Document.case_id)
        .where(Case.firm_id == firm_id)
    )

    return {
        "total_cases": case_count or 0,
        "total_documents": doc_count or 0,
        "anomalies_detected": anomaly_count or 0,
    }
