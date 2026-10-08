from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from db.session import get_session_with_retry as get_session
from models import Firm, User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    firm_name: str
    email: str
    password: str


@router.post("/signup", status_code=201)
async def signup(
    payload: SignupRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    firm = Firm(name=payload.firm_name, plan_tier="free")
    session.add(firm)
    await session.flush()
    user = User(
        firm_id=firm.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="admin",
    )
    session.add(user)
    await session.commit()
    return {"firm_id": str(firm.id), "user_id": str(user.id), "role": user.role}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    return {
        "access_token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    user_id = decode_token(payload.refresh_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
async def change_password(
    payload: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="incorrect current password")
    user.password_hash = hash_password(payload.new_password)
    await session.commit()
    return {"status": "ok"}
