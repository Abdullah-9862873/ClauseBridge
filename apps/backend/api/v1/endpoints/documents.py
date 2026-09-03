import hashlib
import logging
import uuid
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from api.v1.endpoints.cases import _get_owned_case
from core.security import decode_token
from db.session import get_session
from models import Document, User
from storage.s3_client import download_object, upload_file_to_storage
from workers.tasks import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


@router.post("/{case_id}/documents", status_code=201)
async def create_document(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),  # noqa: B008
    idempotency_key: str = Header(...),
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are allowed")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
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

    document_id = uuid.uuid4()
    key = f"cases/{case_id}/{document_id}.pdf"

    try:
        upload_file_to_storage(key, content, "application/pdf")
        from storage.s3_client import s3, settings
        s3.head_object(Bucket=settings.supabase_storage_bucket, Key=key)
    except (ClientError, BotoCoreError) as exc:
        logger.warning("S3 upload failed for %s: %s", key, exc)
        raise HTTPException(
            status_code=503,
            detail="Storage service unavailable — try again",
        ) from exc

    doc = Document(
        id=document_id,
        case_id=case.id,
        filename=file.filename or "document.pdf",
        storage_url=key,
        status="queued",
        file_type="pdf",
        idempotency_key_hash=key_hash,
    )
    session.add(doc)
    await session.commit()
    ingest_document.delay(str(doc.id))

    return {
        "document_id": str(doc.id),
        "status": "queued",
    }


@router.get("/{case_id}/documents")
async def list_documents(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    await _get_owned_case(case_id, user, session)
    result = await session.execute(
        select(Document).where(Document.case_id == uuid.UUID(case_id))
    )
    documents = result.scalars().all()
    return {
        "items": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "status": d.status,
                "document_type": d.document_type,
                "classification_confidence": d.classification_confidence,
                "created_at": d.created_at.isoformat(),
            }
            for d in documents
        ]
    }


@router.get("/{case_id}/documents/{document_id}")
async def get_document(
    case_id: str,
    document_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    await _get_owned_case(case_id, user, session)
    doc = await session.get(Document, document_id)
    if doc is None or str(doc.case_id) != case_id:
        raise HTTPException(status_code=404, detail="document not found")
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "document_type": doc.document_type,
        "classification_confidence": str(doc.classification_confidence) if doc.classification_confidence else None,
        "storage_url": doc.storage_url,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/{case_id}/documents/{document_id}/pdf")
async def get_document_pdf(
    case_id: str,
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: str = Query(...),
) -> StreamingResponse:
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid token")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    await _get_owned_case(case_id, user, session)
    doc = await session.get(Document, document_id)
    if doc is None or str(doc.case_id) != case_id:
        raise HTTPException(status_code=404, detail="document not found")
    if doc.status != "done":
        raise HTTPException(status_code=400, detail="document not ready")
    try:
        data = download_object(doc.storage_url)
    except (ClientError, BotoCoreError) as exc:
        logger.warning("S3 download failed for %s: %s", doc.storage_url, exc)
        raise HTTPException(
            status_code=404,
            detail="PDF file not found in storage",
        ) from exc
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )
