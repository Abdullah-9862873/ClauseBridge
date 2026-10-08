"""Unit tests for services/classification_service.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.classification_service import classify_document


class TestClassifyDocument:
    @pytest.mark.asyncio
    async def test_classify_returns_result(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.classify.return_value = {"type": "NDA", "confidence": 0.95}

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.classification_service.llm", mock_llm),
            patch("services.classification_service.SessionLocal", return_value=mock_session_ctx),
        ):
            result = await classify_document("doc-123", "This is an NDA document...")

        assert result["type"] == "NDA"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_classify_missing_type_raises(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.classify.return_value = {"confidence": 0.8}  # missing "type"

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.classification_service.llm", mock_llm),
            patch("services.classification_service.SessionLocal", return_value=mock_session_ctx),
        ):
            with pytest.raises(ValueError, match="missing required fields"):
                await classify_document("doc-123", "Some text")

    @pytest.mark.asyncio
    async def test_classify_missing_confidence_raises(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.classify.return_value = {"type": "lease"}  # missing "confidence"

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.classification_service.llm", mock_llm),
            patch("services.classification_service.SessionLocal", return_value=mock_session_ctx),
        ):
            with pytest.raises(ValueError, match="missing required fields"):
                await classify_document("doc-123", "Some text")

    @pytest.mark.asyncio
    async def test_classify_updates_db(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.classify.return_value = {"type": "contract", "confidence": 0.88}

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.classification_service.llm", mock_llm),
            patch("services.classification_service.SessionLocal", return_value=mock_session_ctx),
        ):
            await classify_document("doc-456", "Contract text...")

        # Verify DB update was called
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()
