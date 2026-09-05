import base64
import json
import logging
import uuid
from datetime import datetime
from typing import Annotated

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from cache.llm_cache import _redis
from db.session import get_session
from models import Anomaly, Case, Clause, Document, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreateRequest(BaseModel):
    title: str


def _encode_cursor(created_at: datetime, case_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(
        json.dumps([created_at.isoformat(), str(case_id)]).encode()
    ).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    created_at_iso, case_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(created_at_iso), uuid.UUID(case_id)


@router.post("", status_code=201)
async def create_case(
    payload: CaseCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title cannot be empty")
    existing = await session.execute(
        select(Case).where(Case.firm_id == user.firm_id, Case.title == title)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="a case with this title already exists")
    case = Case(firm_id=user.firm_id, title=title)
    session.add(case)
    await session.commit()
    return {"id": str(case.id), "title": case.title}


@router.get("")
async def list_cases(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, object]:
    query = (
        select(Case)
        .where(Case.firm_id == user.firm_id)
        .order_by(Case.created_at.desc(), Case.id)
    )
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                Case.created_at < cursor_created_at,
                (Case.created_at == cursor_created_at) & (Case.id < cursor_id),
            )
        )
    query = query.limit(limit + 1)
    result = await session.execute(query)
    cases = result.scalars().all()
    has_more = len(cases) > limit
    items = cases[:limit]
    next_cursor = (
        _encode_cursor(items[-1].created_at, items[-1].id)
        if has_more and items
        else None
    )
    return {
        "items": [
            {
                "id": str(c.id),
                "title": c.title,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ],
        "next_cursor": next_cursor,
    }


async def _get_owned_case(case_id: str, user: User, session: AsyncSession) -> Case:
    case = await session.get(Case, case_id)
    if case is None or case.firm_id != user.firm_id:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)
    return {"id": str(case.id), "title": case.title, "status": case.status}


class CaseUpdateRequest(BaseModel):
    title: str | None = None
    status: str | None = None


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    payload: CaseUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)
    if payload.title is not None:
        case.title = payload.title
    if payload.status is not None:
        case.status = payload.status
    await session.commit()
    return {"id": str(case.id), "title": case.title, "status": case.status}


@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    case = await _get_owned_case(case_id, user, session)
    case_uuid = case.id
    doc_result = await session.execute(
        select(Document.id).where(Document.case_id == case_uuid)
    )
    doc_ids = [row[0] for row in doc_result.all()]
    deleted_keys = 0
    try:
        keys_to_delete = list(_redis.scan_iter("llm:*"))
        if keys_to_delete:
            pipe = _redis.pipeline()
            for key in keys_to_delete:
                pipe.delete(key)
            deleted_keys = sum(pipe.execute())
    except redis.RedisError:
        logger.warning("failed to clean redis cache")
    if doc_ids:
        clause_result = await session.execute(
            select(Clause.id).where(Clause.document_id.in_(doc_ids))
        )
        clause_ids = [row[0] for row in clause_result.all()]
        if clause_ids:
            await session.execute(
                delete(Anomaly).where(Anomaly.clause_id.in_(clause_ids))
            )
            await session.execute(
                delete(Clause).where(Clause.document_id.in_(doc_ids))
            )
        await session.execute(
            delete(Document).where(Document.id.in_(doc_ids))
        )
    await session.execute(delete(Case).where(Case.id == case_uuid))
    await session.commit()
    logger.info("deleted case %s with %d documents and %d cache keys", case_id, len(doc_ids), deleted_keys)
    return {"deleted": case_id, "documents_deleted": str(len(doc_ids)), "cache_keys_deleted": str(deleted_keys)}
