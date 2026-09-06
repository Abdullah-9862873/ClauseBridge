import base64
import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from db.session import get_session
from models import Anomaly, Clause, Document, User

router = APIRouter(prefix="/cases", tags=["anomalies"])

def _encode_cursor(created_at: datetime, anomaly_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(
        json.dumps([created_at.isoformat(), str(anomaly_id)]).encode()
    ).decode()
def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_at_iso, anomaly_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(created_at_iso), uuid.UUID(anomaly_id)
    except (ValueError, json.JSONDecodeError, uuid.UUIDError):
        raise HTTPException(status_code=400, detail="invalid cursor")
@router.get("/{case_id}/anomalies")
async def list_anomalies(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    document_id: str | None = Query(None),
    severity: str | None = Query(None),
    reviewed: bool | None = Query(None),
) -> dict[str, object]:
    try:
        case_uuid = uuid.UUID(case_id.strip())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="invalid case_id")
    query = (
        select(Anomaly)
        .join(Clause, Clause.id == Anomaly.clause_id)
        .join(Document, Document.id == Clause.document_id)
        .where(Document.case_id == case_uuid)
        .order_by(Anomaly.created_at.desc(), Anomaly.id)
    )
    if document_id:
        try:
            query = query.where(Clause.document_id == uuid.UUID(document_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid document_id")
    if severity:
        query = query.where(Anomaly.severity == severity)
    if reviewed is not None:
        query = query.where(Anomaly.reviewed == reviewed)
    if cursor:
        anchor_time, anchor_id = _decode_cursor(cursor)
        query = query.where(
            (Anomaly.created_at < anchor_time)
            | ((Anomaly.created_at == anchor_time) & (Anomaly.id < anchor_id))
        )
    query = query.limit(limit + 1)
    result = await session.execute(query)
    anomalies = result.scalars().all()
    has_more = len(anomalies) > limit
    items = anomalies[:limit]
    next_cursor = (
        _encode_cursor(items[-1].created_at, items[-1].id)
        if has_more and items
        else None
    )
    return {
        "items": [
            {
                "id": str(a.id),
                "clause_id": str(a.clause_id),
                "severity": a.severity,
                "reasons": a.reasons,
                "confidence": a.confidence,
                "reviewed": a.reviewed,
                "source": a.source,
                "matched_reference": a.matched_reference,
                "verified": a.verified,
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
        "next_cursor": next_cursor,
    }

class AnomalyReviewRequest(BaseModel):
    reviewed: bool

@router.patch("/{case_id}/anomalies/{anomaly_id}/review")
async def mark_reviewed(
    case_id: str,
    anomaly_id: str,
    payload: AnomalyReviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    anomaly = await session.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="anomaly not found")
    clause = await session.get(Clause, anomaly.clause_id)
    if clause is None:
        raise HTTPException(status_code=404, detail="clause not found")
    document = await session.get(Document, clause.document_id)
    if document is None or str(document.case_id) != case_id.strip():
        raise HTTPException(status_code=404, detail="anomaly not found in this case")
    anomaly.reviewed = payload.reviewed
    await session.commit()
    return {"id": str(anomaly.id), "reviewed": str(anomaly.reviewed).lower()}