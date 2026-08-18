import base64
import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from db.session import get_session
from models import Case, User

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
    case = Case(firm_id=user.firm_id, title=payload.title)
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
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)
    await session.delete(case)
    await session.commit()
    return {"deleted": str(case.id)}
