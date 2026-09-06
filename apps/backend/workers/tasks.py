import asyncio
import hashlib
import logging
import time
import uuid

from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from celery import Task  # type: ignore[import-untyped]
from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]
from sqlalchemy import and_, or_, select, update

from db.session import SessionLocal
from models import Document, ReferenceDocument, ReferenceChunk
from services.anomaly_detection_service import detect_anomalies_country_law, detect_anomalies_reference_docs
from services.classification_service import classify_document
from services.clause_extraction_service import extract_and_store_clauses
from services.injection_guard import check_injection
from storage.s3_client import download_object
from workers.celery_app import celery_app
from workers.embeddings import embed_texts
from workers.chunking import split_into_chunks
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


async def _wait_for_reference_docs(case_id: str, timeout: int = 120) -> bool:
    """Wait until all reference documents for this case are done or errored.
    Returns True if all done, False if any errored, timed out, or none exist.
    """
    # First check if there are any reference docs at all
    async with SessionLocal() as session:
        result = await session.execute(
            select(ReferenceDocument.id, ReferenceDocument.status).where(
                ReferenceDocument.case_id == uuid.UUID(case_id),
            )
        )
        rows = result.all()

    if not rows:
        logger.info("no reference documents for case %s, skipping wait", case_id)
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Check for errors — stop waiting immediately
        for ref_id, status in rows:
            if status == "error":
                logger.warning(
                    "reference doc %s has error status, proceeding with available refs",
                    ref_id,
                )
                return False

        # Check if any still pending
        pending = [str(rid) for rid, st in rows if st in ("queued", "processing")]
        if not pending:
            return True
        logger.info(
            "document pipeline: waiting for %d reference doc(s) to finish: %s",
            len(pending),
            pending,
        )
        await asyncio.sleep(3)

        # Re-check statuses
        async with SessionLocal() as session:
            result = await session.execute(
                select(ReferenceDocument.id, ReferenceDocument.status).where(
                    ReferenceDocument.case_id == uuid.UUID(case_id),
                )
            )
            rows = result.all()

    logger.warning("timeout waiting for reference docs in case %s", case_id)
    return False


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
        classification = await classify_document(document_id, text)
        doc_type = classification.get("type", "other")
        if doc_type == "other":
            logger.info("document %s classified as non-legal (%s), skipping extraction", document_id, doc_type)
        else:
            clause_count = await extract_and_store_clauses(document_id, text)
            logger.info("document %s saved %d clauses", document_id, clause_count)
            country = doc.country if hasattr(doc, "country") else None

            country_count = await detect_anomalies_country_law(document_id, country=country)
            logger.info("document %s: %d anomalies from country law (country=%s)", document_id, country_count, country)

            await _wait_for_reference_docs(str(doc.case_id))
            ref_count = await detect_anomalies_reference_docs(document_id, str(doc.case_id))
            logger.info("document %s: %d anomalies from reference docs", document_id, ref_count)

        async with SessionLocal() as session:
            await session.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(content_hash=text_hash)
            )
            await session.commit()
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
    except Exception as exc:
        logger.exception("processing failed for %s (attempt %d)", document_id, self.request.retries + 1)
        if self.request.retries < 3:
            try:
                raise self.retry(countdown=30, exc=exc)
            except MaxRetriesExceededError:
                pass
        asyncio.run(_set_status(document_id, "error"))
        raise
    return document_id


async def _set_ref_status(ref_id: str, new_status: str) -> None:
    async with SessionLocal() as session:
        ref_doc = await session.get(ReferenceDocument, ref_id)
        if ref_doc is None:
            logger.error("reference document %s not found", ref_id)
            return
        ref_doc.status = new_status
        await session.commit()
        logger.info("reference document %s -> %s", ref_id, new_status)


async def _run_ref_pipeline(ref_id: str) -> None:
    await _set_ref_status(ref_id, "processing")
    try:
        async with SessionLocal() as session:
            ref_doc = await session.get(ReferenceDocument, ref_id)
            assert ref_doc is not None
            key = ref_doc.storage_url

        pdf_bytes = download_object(key)
        text = extract_text_from_pdf(pdf_bytes)
        logger.info("reference document %s extracted %d chars", ref_id, len(text))

        chunks = split_into_chunks(text)
        if not chunks:
            logger.info("reference document %s produced 0 chunks", ref_id)
            await _set_ref_status(ref_id, "done")
            return

        vectors = embed_texts(chunks)

        async with SessionLocal() as session:
            for i, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                chunk = ReferenceChunk(
                    reference_document_id=uuid.UUID(ref_id),
                    chunk_text=chunk_text,
                    chunk_index=i,
                    embedding=vector,
                )
                session.add(chunk)
            ref_doc = await session.get(ReferenceDocument, ref_id)
            assert ref_doc is not None
            ref_doc.chunk_count = len(chunks)
            await session.commit()
        logger.info("reference document %s saved %d chunks", ref_id, len(chunks))
    except Exception:
        logger.exception("reference document processing failed for %s", ref_id)
        try:
            await _set_ref_status(ref_id, "error")
        except Exception:
            logger.exception("failed to set error status for ref doc %s", ref_id)
        raise
    await _set_ref_status(ref_id, "done")


@celery_app.task(bind=True, max_retries=3)
def ingest_reference_document(self: Task, ref_id: str) -> str:
    try:
        asyncio.run(_run_ref_pipeline(ref_id))
    except Exception as exc:
        logger.exception("reference document processing failed for %s (attempt %d)", ref_id, self.request.retries + 1)
        if self.request.retries < 2:
            try:
                raise self.retry(countdown=30, exc=exc)
            except MaxRetriesExceededError:
                pass
        asyncio.run(_set_ref_status(ref_id, "error"))
        raise
    return ref_id
