"""Unit tests for services/anomaly_detection_service.py"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.anomaly_detection_service import STANDARD_TEMPLATES, detect_anomalies_for_document

DOC_UUID = str(uuid.uuid4())


def _make_clause(clause_type: str = "termination", text: str = "Clause text here"):
    clause = AsyncMock()
    clause.id = uuid.uuid4()
    clause.clause_type = clause_type
    clause.clause_text = text
    clause.document_id = uuid.UUID(DOC_UUID)
    return clause


class TestDetectAnomaliesForDocument:
    @pytest.mark.asyncio
    async def test_no_clauses_returns_zero(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.anomaly_detection_service.SessionLocal", return_value=mock_session_ctx):
            count = await detect_anomalies_for_document(DOC_UUID)

        assert count == 0

    @pytest.mark.asyncio
    async def test_skips_unknown_clause_types(self) -> None:
        clause = _make_clause(clause_type="unknown_type")
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [clause]
        mock_session.execute.return_value = mock_result
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("services.anomaly_detection_service.SessionLocal", return_value=mock_session_ctx):
            count = await detect_anomalies_for_document(DOC_UUID)

        assert count == 0

    @pytest.mark.asyncio
    async def test_detects_an_anomaly(self) -> None:
        clause = _make_clause(clause_type="termination", text="Immediate termination allowed.")
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": True,
            "severity": "high",
            "reasons": "No notice period specified",
            "confidence": 0.92,
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [clause]
        mock_session.execute.return_value = mock_result
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.anomaly_detection_service.llm", mock_llm),
            patch("services.anomaly_detection_service.SessionLocal", return_value=mock_session_ctx),
        ):
            count = await detect_anomalies_for_document(DOC_UUID)

        assert count == 1
        mock_session.add.assert_called_once()
        anomaly = mock_session.add.call_args[0][0]
        assert anomaly.severity == "high"
        assert anomaly.confidence == 0.92

    @pytest.mark.asyncio
    async def test_no_anomaly_when_standard_matches(self) -> None:
        clause = _make_clause(
            clause_type="termination",
            text="Either party may terminate this agreement with 30 days written notice.",
        )
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": False,
            "severity": "none",
            "reasons": "",
            "confidence": 0.1,
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [clause]
        mock_session.execute.return_value = mock_result
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.anomaly_detection_service.llm", mock_llm),
            patch("services.anomaly_detection_service.SessionLocal", return_value=mock_session_ctx),
        ):
            count = await detect_anomalies_for_document(DOC_UUID)

        assert count == 0
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_passes_standard_template_to_llm(self) -> None:
        clause = _make_clause(clause_type="payment", text="Pay in 15 days.")
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": False, "severity": "none", "reasons": "", "confidence": 0.0,
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [clause]
        mock_session.execute.return_value = mock_result
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("services.anomaly_detection_service.llm", mock_llm),
            patch("services.anomaly_detection_service.SessionLocal", return_value=mock_session_ctx),
        ):
            await detect_anomalies_for_document(DOC_UUID)

        call_kwargs = mock_llm.detect_anomalies.call_args
        assert call_kwargs[1]["clause_type"] == "payment"
        assert call_kwargs[1]["standard_text"] == STANDARD_TEMPLATES["payment"]


class TestStandardTemplates:
    def test_all_expected_types_present(self) -> None:
        expected = {"termination", "liability", "confidentiality", "payment", "dispute_resolution", "intellectual_property", "other"}
        assert set(STANDARD_TEMPLATES.keys()) == expected

    def test_other_template_is_empty(self) -> None:
        assert STANDARD_TEMPLATES["other"] == ""
