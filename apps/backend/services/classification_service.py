import logging
from typing import Any

from sqlalchemy import update

from db.session import CelerySessionLocal as SessionLocal
from llm.groq_provider import GroqProvider
from models.document import Document

logger = logging.getLogger(__name__)
llm = GroqProvider()


async def classify_document(document_id: str, text: str) -> dict[str, Any]:
    """Classify a document and update it in the database.
    Args:
        document_id: The UUID of the document to classify.
        text: The text content of the document.
    Returns:
        The classification result with 'type' and 'confidence'.
    """
    result = await llm.classify(text)
    if "type" not in result or "confidence" not in result:
        raise ValueError("LLM response missing required fields: type, confidence")
    async with SessionLocal() as session:
        await session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(
                document_type=result["type"],
                classification_confidence=result["confidence"],
            )
        )
        await session.commit()
    logger.info(
        "Document %s classified as %s (confidence: %.2f)",
        document_id,
        result["type"],
        result["confidence"],
    )

    return result
