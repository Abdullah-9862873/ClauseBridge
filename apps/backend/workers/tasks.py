import asyncio
import logging
import uuid
import hashlib

from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from celery import Task  # type: ignore[import-untyped]
from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]
from sqlalchemy import select, and_, update

from db.session import SessionLocal
from models import Document
from services.classification_service import classify_document
from services.injection_guard import check_injection
from services.anomaly_detection_service import detect_anomalies_for_document
from storage.s3_client import download_object
from workers.celery_app import celery_app
from services.clause_extraction_service import extract_and_store_clauses
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
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        async with SessionLocal() as session:
            existing = await session.execute(
                select(Document.id)
                .where(and_(
                    Document.case_id == doc.case_id,
                    Document.content_hash == text_hash,
                    Document.id != uuid.UUID(document_id),
                ))
                .limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                logger.info("duplicate content detected for document %s, skipping", document_id)
                await _set_status(document_id, "done")
                return
        await check_injection(text)
        await classify_document(document_id, text)
        clause_count = await extract_and_store_clauses(document_id, text)
        async with SessionLocal() as session:
            await session.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(content_hash=text_hash)
            )
            await session.commit()
        logger.info("document %s saved %d clauses", document_id, clause_count)
        anomalies_found = await detect_anomalies_for_document(document_id)
        logger.info("document %s: %d anomalies found", document_id, anomalies_found)
    except Exception:
        logger.exception("processing failed for %s", document_id)
        raise
    await _set_status(document_id, "done")


@celery_app.task(bind=True, max_retries=6)  # type: ignore[untyped-decorator]
def ingest_document(self: Task, document_id: str) -> str:
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
