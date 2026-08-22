import logging
import uuid
from db.session import SessionLocal
from models.clause import Clause
from workers.chunking import split_into_chunks
from workers.embeddings import embed_texts

logger = logging.getLogger(__name__)

async def extract_and_store_clauses(document_id: str, text: str) -> int:
    """Extract clauses from text, embed them, and store in DB.
    Returns the number of clauses saved.
    """
    chunks = split_into_chunks(text)
    vectors = embed_texts(chunks)
    async with SessionLocal() as session:
        for chunk, vector in zip(chunks, vectors):
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
    return len(chunks)