import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from api.v1.endpoints.cases import _get_owned_case
from db.session import get_session
from models import Document, User
from storage.s3_client import generate_presigned_upload_url
from workers.tasks import ingest_document
from pydantic import BaseModel

router = APIRouter(prefix="/cases", tags=["documents"])


class DocumentCreateRequest(BaseModel):
    file_size: int

@router.post("/{case_id}/documents", status_code=201)
async def create_document(
    case_id: str,
    payload: DocumentCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: str = Header(...),
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
    from sqlalchemy import select
    existing = await session.execute(
        select(Document).where(Document.idempotency_key_hash == key_hash)
    )
    doc = existing.scalar_one_or_none()
    if doc is not None:
        return {
            "document_id": str(doc.id),
            "status": "duplicate",
            "detail": "already received with this Idempotency-Key",
        }
    MAX_SIZE_BYTES = 10 * 1024 * 1024
    if payload.file_size > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="file too large (max 10MB)",
        )
    document_id = uuid.uuid4()
    key = f"cases/{case_id}/{document_id}.pdf"
    doc = Document(
        id=document_id,
        case_id=case.id,
        filename="",
        storage_url=key,
        status="queued",
        file_type="pdf",
        idempotency_key_hash=key_hash,
    )
    session.add(doc)
    await session.commit()
    ingest_document.delay(str(doc.id))
    upload_url = generate_presigned_upload_url(key, "application/pdf")
    return {
        "document_id": str(doc.id),
        "upload_url": upload_url,
        "expires_in": "60s",
        "status": "queued",
    }