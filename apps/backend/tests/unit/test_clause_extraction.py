"""Unit tests for services/clause_extraction_service.py"""

from __future__ import annotations

import sys
import uuid
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

DOC_UUID = str(uuid.uuid4())


def _import_with_mock_embeddings():
    """Import the module after mocking sentence_transformers."""
    fake_st = ModuleType("sentence_transformers")
    fake_st.SentenceTransformer = MagicMock()  # type: ignore[attr-defined]
    sys.modules.setdefault("sentence_transformers", fake_st)
    from services.clause_extraction_service import extract_and_store_clauses
    return extract_and_store_clauses


extract_and_store_clauses = _import_with_mock_embeddings()


class TestExtractAndStoreClauses:
    @pytest.mark.asyncio
    async def test_extracts_and_stores_clauses(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.extract_clauses.return_value = [
            {"clause_type": "termination", "text": "Either party may terminate."},
            {"clause_type": "liability", "text": "Liability capped at fees paid."},
        ]

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.clause_extraction_service.llm", mock_llm),
            patch("services.clause_extraction_service.embed_texts", return_value=[[0.1] * 10, [0.2] * 10]),
            patch("services.clause_extraction_service.SessionLocal", return_value=mock_session_ctx),
        ):
            count = await extract_and_store_clauses(DOC_UUID, "Agreement text...")

        assert count == 2
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_clauses(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.extract_clauses.return_value = []

        with (
            patch("services.clause_extraction_service.llm", mock_llm),
        ):
            count = await extract_and_store_clauses(DOC_UUID, "Short text")

        assert count == 0

    @pytest.mark.asyncio
    async def test_handles_none_clause_type(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.extract_clauses.return_value = [
            {"text": "Some clause without type"},  # missing clause_type
        ]

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.clause_extraction_service.llm", mock_llm),
            patch("services.clause_extraction_service.embed_texts", return_value=[[0.1] * 10]),
            patch("services.clause_extraction_service.SessionLocal", return_value=mock_session_ctx),
        ):
            count = await extract_and_store_clauses(DOC_UUID, "Text")

        assert count == 1
        # The clause should have been created with "other" as fallback type
        added_clause = mock_session.add.call_args[0][0]
        assert added_clause.clause_type == "other"
