from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user, require_admin
from core.security import hash_password
from db.session import get_session_with_retry as get_session
from models import Firm, User

router = APIRouter(prefix="/firms", tags=["firms"])

VALID_ROLES = frozenset({"admin", "attorney", "paralegal"})


class MemberAddRequest(BaseModel):
    email: str
    password: str
    role: str


class RoleRequest(BaseModel):
    role: str


class UpdateFirmRequest(BaseModel):
    name: str


def _invalid_role(role: str) -> bool:
    return role not in VALID_ROLES


@router.get("/me")
async def get_my_firm(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    firm = await session.get(Firm, user.firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="firm not found")
    return {
        "id": str(firm.id),
        "name": firm.name,
        "plan_tier": firm.plan_tier,
    }


@router.patch("/me")
async def update_my_firm(
    payload: UpdateFirmRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    firm = await session.get(Firm, user.firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="firm not found")
    firm.name = payload.name
    await session.commit()
    return {"id": str(firm.id), "name": firm.name, "plan_tier": firm.plan_tier}


@router.post("/members", status_code=201)
async def add_member(
    payload: MemberAddRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    if _invalid_role(payload.role):
        raise HTTPException(
            status_code=422,
            detail="role must be admin, attorney, or paralegal",
        )
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(
        firm_id=admin.firm_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    await session.commit()
    return {"user_id": str(user.id), "role": user.role}


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    target = await session.get(User, user_id)
    if target is None or target.firm_id != admin.firm_id:
        raise HTTPException(status_code=404, detail="member not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="cannot remove yourself")
    await session.delete(target)
    await session.commit()
    return {"deleted": str(target.id)}


@router.patch("/members/{user_id}")
async def change_role(
    user_id: str,
    payload: RoleRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    if _invalid_role(payload.role):
        raise HTTPException(
            status_code=422,
            detail="role must be admin, attorney, or paralegal",
        )
    target = await session.get(User, user_id)
    if target is None or target.firm_id != admin.firm_id:
        raise HTTPException(status_code=404, detail="member not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="cannot change your own role")
    target.role = payload.role
    await session.commit()
    return {"user_id": str(target.id), "role": target.role}
