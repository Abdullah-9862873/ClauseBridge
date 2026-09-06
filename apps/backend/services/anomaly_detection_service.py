import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from db.session import CelerySessionLocal as SessionLocal
from llm.groq_provider import GroqProvider
from models.anomaly import Anomaly
from models.clause import Clause
from models.case import Case
from services.reference_cache_service import get_reference_cache, init_reference_cache
from services.reference_rag_service import format_reference_context

logger = logging.getLogger(__name__)

llm = GroqProvider()

STANDARD_TEMPLATES: dict[str, str] = {
    "termination": "Either party may terminate this agreement with 30 days written notice.",
    "liability": "Total liability shall not exceed the total fees paid under this agreement.",
    "confidentiality": "Both parties shall keep confidential all information received during the term.",
    "payment": "Payment is due within 30 days of invoice date.",
    "dispute_resolution": "Disputes shall be resolved through binding arbitration.",
    "intellectual_property": "All intellectual property created remains with the originating party.",
    "other": "",
}


async def _save_anomaly(
    clause: Clause,
    detection: dict,
    source: str,
    matched_reference: str | None = None,
    verified: bool = True,
) -> bool:
    """Save an anomaly immediately.
    Returns True if the anomaly was saved.
    """
    severity = detection.get("severity", "none")
    reasons = detection.get("reasons", "")
    confidence = detection.get("confidence", 0.0)

    if severity == "none":
        return False

    if confidence < 0.5:
        logger.info(
            "anomaly for clause %s skipped (confidence %.2f < 0.5)",
            clause.id,
            confidence,
        )
        return False

    async with SessionLocal() as session:
        anomaly = Anomaly(
            clause_id=clause.id,
            severity=severity,
            reasons=reasons,
            confidence=confidence,
            source=source,
            matched_reference=matched_reference,
            verified=verified,
        )
        session.add(anomaly)
        await session.commit()
    logger.info(
        "anomaly saved for clause %s: severity=%s, confidence=%.2f, source=%s",
        clause.id,
        severity,
        confidence,
        source,
    )
    return True


async def detect_anomalies_country_law(document_id: str, country: str | None = None) -> int:
    """Detect anomalies for all clauses against country law only (real-time, verified=matched).
    Returns the number of anomalies found.
    """
    try:
        doc_uuid = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
    except (ValueError, TypeError, AttributeError) as e:
        logger.error("invalid UUID in detect_anomalies_country_law: document_id=%s, error=%s", document_id, e)
        return 0

    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == doc_uuid)
        )
        clauses = result.scalars().all()

    if not clauses:
        logger.info("no clauses for document %s, skipping country law check", document_id)
        return 0

    count = 0
    for clause in clauses:
        standard = STANDARD_TEMPLATES.get(clause.clause_type, "")
        if not standard and not country:
            continue
        detection = await llm.detect_anomalies(
            clause_text=clause.clause_text,
            clause_type=clause.clause_type,
            standard_text=standard,
            country_code=country,
        )
        if detection.get("is_anomaly", False):
            source = "country_law" if country else "firm_standard"
            await _save_anomaly(clause, detection, source, verified=False)
            count += 1

    logger.info("document %s country law: %d anomalies out of %d clauses", document_id, count, len(clauses))
    return count


async def detect_anomalies_reference_docs(
    document_id: str, case_id: str
) -> int:
    """Detect anomalies for all clauses against cached reference documents using cache-first approach.
    Returns the number of matched anomalies.
    """
    try:
        doc_uuid = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
        case_uuid = uuid.UUID(case_id) if isinstance(case_id, str) else case_id
    except (ValueError, TypeError, AttributeError) as e:
        logger.error("invalid UUID in detect_anomalies_reference_docs: document_id=%s, case_id=%s, error=%s", document_id, case_id, e)
        return 0

    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == doc_uuid)
        )
        clauses = result.scalars().all()

    if not clauses:
        logger.info("no clauses for document %s, skipping ref doc check", document_id)
        return 0

    # Initialize cache for this case
    async with SessionLocal() as session:
        case_exists = await session.get(Case, case_uuid)
        if case_exists:
            await init_reference_cache(str(case_uuid))

    # Get reference context for each clause from cache
    clause_texts = [c.clause_text for c in clauses]
    cache = get_reference_cache()

    ref_results_list = await cache.get_reference_context_batch(str(case_uuid), clause_texts, top_k=5)

    count = 0
    for clause, ref_results in zip(clauses, ref_results_list):
        if not ref_results:
            continue
        standard = STANDARD_TEMPLATES.get(clause.clause_type, "")
        ref_context = format_reference_context(ref_results)
        top = ref_results[0]
        matched_ref_text = f"[Source: {top['reference_document_name']}]\n{top['chunk_text']}"
        detection = await llm.detect_anomalies(
            clause_text=clause.clause_text,
            clause_type=clause.clause_type,
            standard_text=standard,
            reference_context=ref_context,
        )
        if detection.get("is_anomaly", False):
            await _save_anomaly(clause, detection, "reference_doc", matched_ref_text, verified=False)
            count += 1

    logger.info("document %s ref docs: %d anomalies out of %d clauses", document_id, count, len(clauses))
    return count