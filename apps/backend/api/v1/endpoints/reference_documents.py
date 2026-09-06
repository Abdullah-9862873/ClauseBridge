import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from api.v1.endpoints.cases import _get_owned_case
from db.session import get_session_with_retry as get_session
from models import ReferenceDocument, ReferenceChunk, User
from storage.s3_client import upload_file_to_storage, download_object
from workers.tasks import ingest_reference_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["reference-documents"])

MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


@router.post("/{case_id}/reference-documents", status_code=201)
async def create_reference_document(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
) -> dict[str, str]:
    case = await _get_owned_case(case_id, user, session)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are allowed")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    document_id = uuid.uuid4()
    key = f"cases/{case_id}/refs/{document_id}.pdf"

    try:
        upload_file_to_storage(key, content, "application/pdf")
    except Exception as exc:
        logger.warning("S3 upload failed for ref doc %s: %s", key, exc)
        raise HTTPException(
            status_code=503,
            detail="Storage service unavailable — try again",
        ) from exc

    ref_doc = ReferenceDocument(
        id=document_id,
        case_id=case.id,
        filename=file.filename or "reference.pdf",
        storage_url=key,
        status="queued",
        chunk_count=0,
    )
    session.add(ref_doc)
    await session.commit()

    ingest_reference_document.delay(str(ref_doc.id))

    return {
        "reference_document_id": str(ref_doc.id),
        "status": "queued",
    }


@router.get("/{case_id}/reference-documents")
async def list_reference_documents(
    case_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    await _get_owned_case(case_id, user, session)
    result = await session.execute(
        select(ReferenceDocument).where(
            ReferenceDocument.case_id == uuid.UUID(case_id)
        )
    )
    ref_docs = result.scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "filename": r.filename,
                "status": r.status,
                "chunk_count": r.chunk_count,
                "created_at": r.created_at.isoformat(),
            }
            for r in ref_docs
        ]
    }


@router.delete("/{case_id}/reference-documents/{ref_id}")
async def delete_reference_document(
    case_id: str,
    ref_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    await _get_owned_case(case_id, user, session)
    ref_uuid = uuid.UUID(ref_id)
    ref_doc = await session.get(ReferenceDocument, ref_uuid)
    if ref_doc is None or str(ref_doc.case_id) != case_id:
        raise HTTPException(status_code=404, detail="reference document not found")

    # Delete chunks first
    await session.execute(
        select(ReferenceChunk).where(ReferenceChunk.reference_document_id == ref_uuid)
    )
    # CASCADE should handle chunk deletion, but let's be explicit
    from sqlalchemy import delete as sa_delete
    await session.execute(
        sa_delete(ReferenceChunk).where(ReferenceChunk.reference_document_id == ref_uuid)
    )
    await session.execute(
        sa_delete(ReferenceDocument).where(ReferenceDocument.id == ref_uuid)
    )
    await session.commit()

    return {"deleted": ref_id}
