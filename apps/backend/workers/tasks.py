from models import Clause
from workers.chunking import split_into_chunks
from workers.embeddings import embed_texts

import uuid
import asyncio
import logging

from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]

from db.session import SessionLocal
from models import Document
from storage.s3_client import download_object
from workers.celery_app import celery_app
from workers.pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)


def _is_missing_file(exc: ClientError) -> bool:
    status: int = exc.response["ResponseMetadata"]["HTTPStatusCode"]
    return status == 404


async def _set_status(document_id: str, new_status: str) -> None:
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            logger.error("document %s not found", document_id)
            return
        doc.status = new_status
        await session.commit()
        logger.info("document %s -> %s", document_id, new_status)


async def _run_pipeline(document_id: str) -> None:
    await _set_status(document_id, "processing")
    try:
        async with SessionLocal() as session:
            doc = await session.get(Document, document_id)
            assert doc is not None
            key = doc.storage_url
        pdf_bytes = download_object(key)
        text = extract_text_from_pdf(pdf_bytes)
        logger.info("document %s extracted %d chars", document_id, len(text))
        chunks = split_into_chunks(text)
        vectors = embed_texts(chunks)
        async with SessionLocal() as session:
            for position, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
                clause = Clause(
                    document_id=uuid.UUID(document_id),
                    clause_text=chunk,
                    clause_type="general",
                    page_number=1,
                    embedding=vector,
                )
                session.add(clause)
            await session.commit()
        logger.info("document %s saved %d clauses", document_id, len(chunks))
    except Exception:
        logger.exception("processing failed for %s", document_id)
        raise
    await _set_status(document_id, "done")

@celery_app.task(bind=True, max_retries=6)  # type: ignore[untyped-decorator]
def ingest_document(self, document_id: str) -> str:
    try:
        asyncio.run(_run_pipeline(document_id))
    except ClientError as exc:
        if _is_missing_file(exc):
            logger.warning(
                "object not in storage yet (attempt %d/6), retrying in 10s",
                self.request.retries,
            )
            try:
                raise self.retry(countdown=10, exc=exc)
            except MaxRetriesExceededError:
                pass
        asyncio.run(_set_status(document_id, "error"))
        raise
    except Exception:
        logger.exception("processing failed for %s", document_id)
        asyncio.run(_set_status(document_id, "error"))
        raise
    return document_id
