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
    applicable_law = detection.get("applicable_law", "")

    if severity == "none":
        return False

    if confidence < 0.3:
        logger.info(
            "anomaly for clause %s skipped (confidence %.2f < 0.3)",
            clause.id,
            confidence,
        )
        return False

    # Enhanced reasons to include the applicable law
    enhanced_reasons = reasons
    if applicable_law and applicable_law not in reasons:
        enhanced_reasons = f"{reasons}\n\nApplicable law: {applicable_law}"

    # reasons column is TEXT type, no practical limit

    async with SessionLocal() as session:
        anomaly = Anomaly(
            clause_id=clause.id,
            severity=severity,
            reasons=enhanced_reasons,
            confidence=confidence,
            source=source,
            matched_reference=matched_reference,
            verified=verified,
        )
        session.add(anomaly)
        await session.commit()
    logger.info(
        "anomaly saved for clause %s: severity=%s, confidence=%.2f, source=%s, law=%s",
        clause.id,
        severity,
        confidence,
        source,
        applicable_law or "N/A",
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


async def detect_document_level_anomalies(document_id: str, country: str | None = None) -> int:
    """Detect anomalies at the FULL DOCUMENT level — catches cross-paragraph contradictions
    and violations that span multiple clauses. This is critical for legal documents where
    contradictions exist between different parts of the same document.
    Returns the number of document-level anomalies found.
    """
    try:
        doc_uuid = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
    except (ValueError, TypeError, AttributeError) as e:
        logger.error("invalid UUID in detect_document_level_anomalies: document_id=%s, error=%s", document_id, e)
        return 0

    if not country:
        logger.info("no country specified, skipping document-level analysis")
        return 0

    # Load ALL clauses and combine them into the full document text
    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == doc_uuid).order_by(Clause.page_number)
        )
        clauses = result.scalars().all()

    if not clauses:
        logger.info("no clauses for document %s, skipping document-level check", document_id)
        return 0

    # Combine all clauses into the full document text
    full_document_text = "\n\n".join(
        f"[Clause {i+1} - {c.clause_type}]\n{c.clause_text}"
        for i, c in enumerate(clauses)
    )

    logger.info("running document-level analysis for %s with %d clauses", document_id, len(clauses))

    # Run the LLM analysis on the FULL document
    detection = await llm.detect_anomalies(
        clause_text=full_document_text,
        clause_type="legal_document",
        standard_text="",
        country_code=country,
    )

    if not detection.get("is_anomaly", False):
        logger.info("document %s: no document-level anomalies detected", document_id)
        return 0

    # Document-level anomalies are attached to the first clause for visibility
    first_clause = clauses[0]
    source = "document_level_country_law"
    await _save_anomaly(first_clause, detection, source, verified=True)
    logger.info(
        "document %s: %d document-level anomaly detected (severity=%s, confidence=%.2f, law=%s)",
        document_id, 1, detection.get("severity"), detection.get("confidence", 0.0),
        detection.get("applicable_law", "N/A"),
    )
    return 1


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