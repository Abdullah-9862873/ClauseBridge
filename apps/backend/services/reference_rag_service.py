import logging
import uuid

from sqlalchemy import select

from db.session import SessionLocal
from models.clause import Clause
from models.reference_chunk import ReferenceChunk
from models.reference_document import ReferenceDocument
from workers.embeddings import embed_texts

logger = logging.getLogger(__name__)

SEARCH_TOP_K = 5
RELEVANCE_THRESHOLD = 0.3


async def _load_reference_chunks(case_id: str) -> tuple[list, dict[str, str]]:
    """Load all reference chunks for a case. Returns (chunks, {ref_id: filename})."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(ReferenceDocument.id, ReferenceDocument.filename).where(
                ReferenceDocument.case_id == uuid.UUID(case_id),
                ReferenceDocument.status == "done",
            )
        )
        rows = result.all()
        ref_ids = [row[0] for row in rows]
        filename_map = {str(row[0]): row[1] for row in rows}

    if not ref_ids:
        return [], {}

    async with SessionLocal() as session:
        result = await session.execute(
            select(ReferenceChunk).where(
                ReferenceChunk.reference_document_id.in_(ref_ids),
                ReferenceChunk.embedding.isnot(None),
            )
        )
        return list(result.scalars().all()), filename_map


def _cosine_search(query_vector: list[float], chunks: list, filename_map: dict[str, str], top_k: int = SEARCH_TOP_K) -> list[dict]:
    """Score chunks against a query vector using cosine similarity."""
    scored = []
    for chunk in chunks:
        if chunk.embedding is None:
            continue
        similarity = sum(a * b for a, b in zip(query_vector, chunk.embedding))
        if similarity >= RELEVANCE_THRESHOLD:
            ref_id = str(chunk.reference_document_id)
            scored.append({
                "chunk_text": chunk.chunk_text,
                "similarity": similarity,
                "chunk_index": chunk.chunk_index,
                "reference_document_id": ref_id,
                "reference_document_name": filename_map.get(ref_id, "Unknown"),
            })
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


async def search_reference_chunks(
    case_id: str,
    clause_text: str,
    top_k: int = SEARCH_TOP_K,
) -> list[dict]:
    """Search reference document chunks for relevant context using vector similarity."""
    chunks, filename_map = await _load_reference_chunks(case_id)
    if not chunks:
        return []

    query_vector = embed_texts([clause_text])[0]
    return _cosine_search(query_vector, chunks, filename_map, top_k)


async def search_reference_chunks_batch(
    case_id: str,
    clause_texts: list[str],
    top_k: int = SEARCH_TOP_K,
) -> list[list[dict]]:
    """Batch embed all clauses and search reference chunks. Returns one result list per clause."""
    chunks, filename_map = await _load_reference_chunks(case_id)
    if not chunks or not clause_texts:
        return [[] for _ in clause_texts]

    query_vectors = embed_texts(clause_texts)
    return [_cosine_search(qv, chunks, filename_map, top_k) for qv in query_vectors]


def format_reference_context(chunks: list[dict]) -> str:
    """Format reference chunks into a context string for the LLM."""
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[Reference {i}] (similarity: {chunk['similarity']:.2f})\n{chunk['chunk_text']}")
    return "\n\n".join(parts)
