from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.v1.deps import get_current_user
from db.session import get_session
from models import Clause, Document, User
from fastapi import HTTPException
import base64
import json
from datetime import datetime
from sqlalchemy import or_


router = APIRouter(prefix="/cases", tags=["clauses"])

@router.get("/{case_id}/documents/{document_id}/clauses")

async def list_clauses(
    case_id: str,
    document_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List clauses for a document with cursor pagination."""
    # Verify document exists and belongs to user's firm
    doc = await session.get(Document, document_id)
    if doc is None or str(doc.case_id) != case_id:
        raise HTTPException(status_code=404, detail="document not found")
    # Build query
    query = (
        select(Clause)
        .where(Clause.document_id == document_id)
        .order_by(Clause.created_at.desc(), Clause.id.desc())
        .limit(limit + 1)
    )
    
    if cursor:
        decoded = json.loads(base64.b64decode(cursor))
        anchor_time = datetime.fromisoformat(decoded[0])
        anchor_id = decoded[1]
        query = query.where(
            or_(
                Clause.created_at < anchor_time,
                (Clause.created_at == anchor_time) & (Clause.id < anchor_id),
            )
        )
    result = await session.execute(query)
    clauses = list(result.scalars().all())
    # Check if there are more results
    has_next = len(clauses) > limit
    if has_next:
        clauses = clauses[:limit]
    # Build next cursor
    next_cursor = None
    if has_next and clauses:
        last = clauses[-1]
        import base64
        import json
        next_cursor = base64.b64encode(
            json.dumps([last.created_at.isoformat(), str(last.id)]).encode()
        ).decode()
    return {
        "items": [
            {
                "id": str(c.id),
                "clause_text": c.clause_text,
                "clause_type": c.clause_type,
                "page_number": c.page_number,
                "created_at": c.created_at.isoformat(),
            }
            for c in clauses
        ],
        "next_cursor": next_cursor,
    }