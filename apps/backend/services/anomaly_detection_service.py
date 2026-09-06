import asyncio
import logging
import uuid

from sqlalchemy import select

from db.session import SessionLocal
from llm.groq_provider import GroqProvider
from models.anomaly import Anomaly
from models.clause import Clause
from models.case import Case
from services.reference_rag_service import search_reference_chunks_batch, format_reference_context

logger = logging.getLogger(__name__)

llm = GroqProvider()

VERIFY_CONFIDENCE_THRESHOLD = 0.7

STANDARD_TEMPLATES: dict[str, str] = {
    "termination": "Either party may terminate this agreement with 30 days written notice.",
    "liability": "Total liability shall not exceed the total fees paid under this agreement.",
    "confidentiality": "Both parties shall keep confidential all information received during the term.",
    "payment": "Payment is due within 30 days of invoice date.",
    "dispute_resolution": "Disputes shall be resolved through binding arbitration.",
    "intellectual_property": "All intellectual property created remains with the originating party.",
    "other": "",
}


async def _verify_and_save_anomaly(
    clause: Clause,
    detection: dict,
    source: str,
    matched_reference: str | None = None,
) -> bool:
    """Verify an anomaly detection result and save if trustworthy.
    Returns True if the anomaly was saved.
    """
    severity = detection.get("severity", "none")
    reasons = detection.get("reasons", "")
    confidence = detection.get("confidence", 0.0)

    if severity == "none":
        return False

    # Skip verification for low-confidence detections
    if confidence < VERIFY_CONFIDENCE_THRESHOLD:
        logger.info(
            "anomaly for clause %s skipped verification (confidence %.2f < %.2f)",
            clause.id, confidence, VERIFY_CONFIDENCE_THRESHOLD,
        )
        return False

    verification = await llm.verify_anomaly(
        clause_text=clause.clause_text,
        clause_type=clause.clause_type,
        severity=severity,
        reasons=reasons,
        source=source,
        matched_reference=matched_reference,
    )

    verified = verification.get("verified", False)
    adj = verification.get("confidence_adjustment", 0.0)
    adjusted_confidence = max(0.0, min(1.0, confidence + adj))

    if not verified:
        logger.info(
            "anomaly for clause %s failed verification (reasons: %s), skipping",
            clause.id, reasons[:100],
        )
        return False

    async with SessionLocal() as session:
        anomaly = Anomaly(
            clause_id=clause.id,
            severity=severity,
            reasons=reasons,
            confidence=adjusted_confidence,
            source=source,
            matched_reference=matched_reference,
            verified=True,
        )
        session.add(anomaly)
        await session.commit()
    logger.info(
        "verified anomaly saved for clause %s: severity=%s, confidence=%.2f, source=%s",
        clause.id, severity, adjusted_confidence, source,
    )
    return True


async def _process_single_clause(
    clause: Clause,
    ref_results: list[dict] | None,
    country: str | None,
) -> int:
    """Process a single clause for anomaly detection. Returns 1 if anomaly saved, 0 otherwise."""
    standard = STANDARD_TEMPLATES.get(clause.clause_type, "")

    # Layer 1: Check against reference documents
    if ref_results:
        ref_context = format_reference_context(ref_results)
        top = ref_results[0]
        matched_ref_text = f"[Source: {top['reference_document_name']}]\n{top['chunk_text']}"
        detection = await llm.detect_anomalies(
            clause_text=clause.clause_text,
            clause_type=clause.clause_type,
            standard_text=standard,
            country_code=country,
            reference_context=ref_context,
        )
        if detection.get("is_anomaly", False):
            source = "reference_doc"
            saved = await _verify_and_save_anomaly(clause, detection, source, matched_ref_text)
            return 1 if saved else 0
        return 0

    # Layer 2: Check against country law (existing logic)
    if not standard and not country:
        return 0
    detection = await llm.detect_anomalies(
        clause_text=clause.clause_text,
        clause_type=clause.clause_type,
        standard_text=standard,
        country_code=country,
    )
    if detection.get("is_anomaly", False):
        source = "country_law" if country else "firm_standard"
        saved = await _verify_and_save_anomaly(clause, detection, source)
        return 1 if saved else 0
    return 0


async def detect_anomalies_for_document(document_id: str, country: str | None = None) -> int:
    """Detect anomalies for all clauses in a document using two-layer approach.
    Optimized: batch embeds all clauses, processes up to 5 in parallel.
    Returns the number of verified anomalies found.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == uuid.UUID(document_id))
        )
        clauses = result.scalars().all()

        from models.document import Document
        doc = await session.get(Document, document_id)
        case_id = str(doc.case_id) if doc else None

    if not clauses:
        logger.info("no clauses found for document %s, skipping anomaly detection", document_id)
        return 0

    # Batch embed all clause texts for reference search (one embedding call)
    ref_results_list = [[] for _ in clauses]
    if case_id:
        clause_texts = [c.clause_text for c in clauses]
        ref_results_list = await search_reference_chunks_batch(case_id, clause_texts)

    # Process clauses in parallel (max 5 concurrent LLM calls)
    sem = asyncio.Semaphore(5)

    async def _bounded_process(clause, ref_results):
        async with sem:
            return await _process_single_clause(clause, ref_results, country)

    results = await asyncio.gather(
        *[_bounded_process(c, r) for c, r in zip(clauses, ref_results_list)]
    )

    anomalies_found = sum(results)
    logger.info(
        "document %s: %d verified anomalies found out of %d clauses",
        document_id, anomalies_found, len(clauses),
    )
    return anomalies_found
