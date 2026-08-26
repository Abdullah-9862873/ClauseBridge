import logging
import uuid

from sqlalchemy import select

from db.session import SessionLocal
from llm.groq_provider import GroqProvider
from models.anomaly import Anomaly
from models.clause import Clause

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
async def detect_anomalies_for_document(document_id: str) -> int:
    """Detect anomalies for all clauses in a document.
    Returns the number of anomalies found.
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(Clause).where(Clause.document_id == uuid.UUID(document_id))
        )
        clauses = result.scalars().all()
    if not clauses:
        logger.info("no clauses found for document %s, skipping anomaly detection", document_id)
        return 0
    anomalies_found = 0
    for clause in clauses:
        standard = STANDARD_TEMPLATES.get(clause.clause_type, "")
        if not standard:
            continue
        detection = await llm.detect_anomalies(
            clause_text=clause.clause_text,
            clause_type=clause.clause_type,
            standard_text=standard,
        )
        if detection.get("is_anomaly", False):
            async with SessionLocal() as session:
                anomaly = Anomaly(
                    clause_id=clause.id,
                    severity=detection.get("severity", "none"),
                    reasons=detection.get("reasons", ""),
                    confidence=detection.get("confidence", 0.0),
                )
                session.add(anomaly)
                await session.commit()
            anomalies_found += 1
            logger.info(
                "anomaly detected for clause %s: severity=%s, confidence=%.2f",
                clause.id, detection.get("severity"), detection.get("confidence"),
            )
    logger.info("document %s: %d anomalies found out of %d clauses", document_id, anomalies_found, len(clauses))
    return anomalies_found
