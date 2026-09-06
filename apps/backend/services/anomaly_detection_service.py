import asyncio
import logging
import uuid

from sqlalchemy import select

from db.session import CelerySessionLocal as SessionLocal
from llm.groq_provider import GroqProvider
from models.anomaly import Anomaly
from models.clause import Clause
from models.case import Case
from services.reference_rag_service import search_reference_chunks_batch, format_reference_context

logger = logging.getLogger(__name__)

llm = GroqProvider()

VERIFY_CONFIDENCE_THRESHOLD = 0.7
VERIFICATION_ATTEMPTS = 3

STANDARD_TEMPLATES: dict[str, str] = {
    "termination": "Either party may terminate this agreement with 30 days written notice.",
    "liability": "Total liability shall not exceed the total fees paid under this agreement.",
    "confidentiality": "Both parties shall keep confidential all information received during the term.",
    "payment": "Payment is due within 30 days of invoice date.",
    "dispute_resolution": "Disputes shall be resolved through binding arbitration.",
    "intellectual_property": "All intellectual property created remains with the originating party.",
    "other": "",
}


async def _verify_3x_and_save(
    clause: Clause,
    detection: dict,
    source: str,
    matched_reference: str | None = None,
) -> bool:
    """Verify an anomaly 3 times for hallucination. Only save if ALL 3 pass.
    Returns True if the anomaly was saved.
    """
    severity = detection.get("severity", "none")
    reasons = detection.get("reasons", "")
    confidence = detection.get("confidence", 0.0)

    if severity == "none":
        return False

    if confidence < VERIFY_CONFIDENCE_THRESHOLD:
        logger.info(
            "anomaly for clause %s skipped (confidence %.2f < %.2f)",
            clause.id, confidence, VERIFY_CONFIDENCE_THRESHOLD,
        )
        return False

    adjusted_confidence = confidence
    for attempt in range(1, VERIFICATION_ATTEMPTS + 1):
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
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence + adj))

        if not verified:
            logger.info(
                "anomaly for clause %s FAILED verification attempt %d/%d, rejecting",
                clause.id, attempt, VERIFICATION_ATTEMPTS,
            )
            return False
        logger.debug(
            "anomaly for clause %s passed verification %d/%d",
            clause.id, attempt, VERIFICATION_ATTEMPTS,
        )

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
        "3x-verified anomaly saved for clause %s: severity=%s, confidence=%.2f, source=%s",
        clause.id, severity, adjusted_confidence, source,
    )
    return True


async def detect_anomalies_country_law(document_id: str, country: str | None = None) -> int:
    """Detect anomalies for all clauses against country law only (no reference docs).
    Each anomaly is verified 3 times before saving.
    Returns the number of verified anomalies found.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == uuid.UUID(document_id))
        )
        clauses = result.scalars().all()

    if not clauses:
        logger.info("no clauses for document %s, skipping country law check", document_id)
        return 0

    sem = asyncio.Semaphore(5)

    async def _process_one(clause: Clause) -> bool:
        async with sem:
            standard = STANDARD_TEMPLATES.get(clause.clause_type, "")
            if not standard and not country:
                return False
            detection = await llm.detect_anomalies(
                clause_text=clause.clause_text,
                clause_type=clause.clause_type,
                standard_text=standard,
                country_code=country,
            )
            if detection.get("is_anomaly", False):
                source = "country_law" if country else "firm_standard"
                return await _verify_3x_and_save(clause, detection, source)
            return False

    results = await asyncio.gather(*[_process_one(c) for c in clauses])
    count = sum(results)
    logger.info("document %s country law: %d anomalies out of %d clauses", document_id, count, len(clauses))
    return count


async def detect_anomalies_reference_docs(document_id: str, case_id: str) -> int:
    """Detect anomalies for all clauses against reference documents only.
    Each anomaly is verified 3 times before saving.
    Returns the number of verified anomalies found.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == uuid.UUID(document_id))
        )
        clauses = result.scalars().all()

    if not clauses:
        logger.info("no clauses for document %s, skipping ref doc check", document_id)
        return 0

    clause_texts = [c.clause_text for c in clauses]
    ref_results_list = await search_reference_chunks_batch(case_id, clause_texts)

    sem = asyncio.Semaphore(5)

    async def _process_one(clause: Clause, ref_results: list[dict]) -> bool:
        async with sem:
            if not ref_results:
                return False
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
                return await _verify_3x_and_save(clause, detection, "reference_doc", matched_ref_text)
            return False

    results = await asyncio.gather(
        *[_process_one(c, r) for c, r in zip(clauses, ref_results_list)]
    )
    count = sum(results)
    logger.info("document %s ref docs: %d anomalies out of %d clauses", document_id, count, len(clauses))
    return count
