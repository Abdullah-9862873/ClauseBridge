import logging
import uuid

from db.session import SessionLocal
from llm.groq_provider import GroqProvider
from models.clause import Clause
from workers.embeddings import embed_texts

llm = GroqProvider()

logger = logging.getLogger(__name__)

async def extract_and_store_clauses(document_id: str, text: str) -> int:
    clauses_data = await llm.extract_clauses(text)
    if not clauses_data:
        return 0
    texts = [c["text"] for c in clauses_data]
    vectors = embed_texts(texts)
    async with SessionLocal() as session:
        for clause_dict, vector in zip(clauses_data, vectors):
            clause_type = (clause_dict.get("clause_type") or clause_dict.get("title") or "other").lower()
            clause = Clause(
                document_id=uuid.UUID(document_id),
                clause_text=clause_dict["text"],
                clause_type=clause_type,
                page_number=1,
                embedding=vector,
            )
            session.add(clause)
        await session.commit()
    return len(clauses_data)