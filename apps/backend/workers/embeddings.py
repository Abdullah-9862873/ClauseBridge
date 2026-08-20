import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
EMBEDDING_DIMENSIONS = 1024
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("loading embedding model %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _get_model().encode(texts, normalize_embeddings=True)
    result: list[list[float]] = [v.tolist() for v in vectors]
    logger.info("embedded %d chunks (%d dims each)", len(result), len(result[0]))
    return result
