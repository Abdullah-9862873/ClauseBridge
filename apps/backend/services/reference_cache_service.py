import asyncio
import logging
import uuid
from typing import TYPE_CHECKING
from collections import defaultdict

import numpy as np
from sqlalchemy import select

from db.session import CelerySessionLocal as SessionLocal
from models.reference_chunk import ReferenceChunk
from models.reference_document import ReferenceDocument
from workers.embeddings import embed_texts

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from models.anomaly import Anomaly


class ReferenceCacheService:
    """In-memory cache for reference document vectors for fast matching."""

    def __init__(self):
        self._cache: dict[str, dict[str, list[tuple[str, np.ndarray, int]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._filename_map: dict[str, dict[str, str]] = defaultdict(dict)
        self._mutex = asyncio.Lock()

    async def populate_cache(self, case_id: str) -> int:
        """Load all reference chunks into memory cache."""
        try:
            case_uuid = uuid.UUID(case_id) if isinstance(case_id, str) else case_id
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("invalid case_id for populate_cache: %s, error: %s", case_id, e)
            return 0

        async with self._mutex:
            async with SessionLocal() as session:
                result = await session.execute(
                    select(
                        ReferenceDocument.id,
                        ReferenceDocument.filename,
                        ReferenceChunk.chunk_text,
                        ReferenceChunk.embedding,
                        ReferenceChunk.chunk_index,
                    ).where(
                        ReferenceDocument.case_id == case_uuid,
                        ReferenceDocument.status == "done",
                        ReferenceChunk.embedding.isnot(None),
                    )
                )
                rows = result.all()

            if not rows:
                return 0

            for ref_doc_id, filename, chunk_text, embedding, chunk_index in rows:
                if embedding:
                    self._cache[case_id][ref_doc_id].append(
                        (chunk_text, np.array(embedding), chunk_index)
                    )
                    self._filename_map[case_id][ref_doc_id] = filename

            logger.info(
                "loaded %d reference documents into cache for case %s",
                len(self._cache[case_id]),
                case_id,
            )
            return len(self._cache[case_id])

    async def get_reference_context(
        self, case_id: str, clause_text: str, top_k: int = 5
    ) -> list[dict]:
        """Get top-k most relevant reference chunks for a clause using cosine similarity."""
        if case_id not in self._cache or not self._cache[case_id]:
            return []

        query_vector = embed_texts([clause_text])[0]

        similarities = []
        for ref_doc_id, chunks in self._cache[case_id].items():
            for chunk_text, chunk_vector, chunk_index in chunks:
                similarity = float(np.dot(query_vector, chunk_vector))
                filename = self._filename_map[case_id].get(ref_doc_id, "Unknown")
                similarities.append({
                    "chunk_text": chunk_text,
                    "similarity": similarity,
                    "chunk_index": chunk_index,
                    "reference_document_id": ref_doc_id,
                    "reference_document_name": filename,
                })

        relevants = sorted(
            [s for s in similarities if s["similarity"] >= 0.3],
            key=lambda x: x["similarity"],
            reverse=True,
        )[:top_k]

        logger.debug(
            "found %d relevant references for clause '%s[:50]...'",
            len(relevants),
            clause_text[:50],
        )
        return relevants

    async def get_reference_context_batch(
        self, case_id: str, clause_texts: list[str], top_k: int = 5
    ) -> list[list[dict]]:
        """Batch query references for multiple clauses."""
        if case_id not in self._cache or not self._cache[case_id]:
            return [[] for _ in clause_texts]

        query_vectors = embed_texts(clause_texts)

        results = []
        for query_vector in query_vectors:
            similarities = []
            for ref_doc_id, chunks in self._cache[case_id].items():
                for chunk_text, chunk_vector, chunk_index in chunks:
                    similarity = float(np.dot(query_vector, chunk_vector))
                    filename = self._filename_map[case_id].get(ref_doc_id, "Unknown")
                    similarities.append({
                        "chunk_text": chunk_text,
                        "similarity": similarity,
                        "chunk_index": chunk_index,
                        "reference_document_id": ref_doc_id,
                        "reference_document_name": filename,
                    })

            relevants = sorted(
                [s for s in similarities if s["similarity"] >= 0.3],
                key=lambda x: x["similarity"],
                reverse=True,
            )[:top_k]
            results.append(relevants)

        return results


_reference_cache = ReferenceCacheService()


def get_reference_cache() -> ReferenceCacheService:
    """Get the singleton reference cache instance."""
    return _reference_cache


async def init_reference_cache(case_id: str) -> None:
    """Initialize cache for a case (should be called when case is created)."""
    count = await get_reference_cache().populate_cache(case_id)
    logger.info("initialized reference cache for case %s: %d docs", case_id, count)