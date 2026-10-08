"""Unit tests for services/anomaly_detection_service.py"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.anomaly_detection_service import STANDARD_TEMPLATES, detect_anomalies_country_law, detect_anomalies_reference_docs

DOC_UUID = str(uuid.uuid4())


def _make_clause(clause_type: str = "termination", text: str = "Clause text here"):
    clause = AsyncMock()
    clause.id = uuid.uuid4()
    clause.clause_type = clause_type
    clause.clause_text = text
    clause.document_id = uuid.UUID(DOC_UUID)
    return clause


def _make_doc(case_id=None):
    doc = AsyncMock()
    doc.id = uuid.UUID(DOC_UUID)
    doc.case_id = case_id or uuid.uuid4()
    return doc


def _mock_verify_verified():
    """Return a mock verify_anomaly that returns verified=True (works for all 3 calls)."""
    mock = AsyncMock()
    mock.return_value = {"verified": True, "confidence_adjustment": 0.05}
    return mock


def _mock_verify_rejected():
    """Return a mock verify_anomaly that returns verified=False."""
    mock = AsyncMock()
    mock.return_value = {"verified": False, "confidence_adjustment": -0.2}
    return mock


def _mock_verify_fails_on_third():
    """Return a mock that passes 2 verifications then fails on 3rd."""
    mock = AsyncMock()
    mock.side_effect = [
        {"verified": True, "confidence_adjustment": 0.05},
        {"verified": True, "confidence_adjustment": 0.05},
        {"verified": False, "confidence_adjustment": -0.2},
    ]
    return mock


class TestDetectAnomaliesCountryLaw:
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
            count = await detect_anomalies_country_law(DOC_UUID)

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
            count = await detect_anomalies_country_law(DOC_UUID)

        assert count == 0

    @pytest.mark.asyncio
    async def test_detects_anomaly_with_3x_verification(self) -> None:
        clause = _make_clause(clause_type="termination", text="Immediate termination allowed.")
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": True,
            "severity": "high",
            "reasons": "No notice period specified",
            "confidence": 0.92,
        }
        mock_llm.verify_anomaly = _mock_verify_verified()

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
            count = await detect_anomalies_country_law(DOC_UUID)

        assert count == 1
        mock_session.add.assert_called_once()
        assert mock_llm.verify_anomaly.call_count == 3
        anomaly = mock_session.add.call_args[0][0]
        assert anomaly.severity == "high"
        assert anomaly.verified is True

    @pytest.mark.asyncio
    async def test_rejects_if_any_verification_fails(self) -> None:
        clause = _make_clause(clause_type="termination", text="Standard termination clause.")
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": True,
            "severity": "medium",
            "reasons": "Violates some made-up law",
            "confidence": 0.75,
        }
        mock_llm.verify_anomaly = _mock_verify_fails_on_third()

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
            count = await detect_anomalies_country_law(DOC_UUID)

        assert count == 0
        mock_session.add.assert_not_called()
        assert mock_llm.verify_anomaly.call_count == 3

    @pytest.mark.asyncio
    async def test_rejects_immediately_on_first_failure(self) -> None:
        clause = _make_clause(clause_type="termination", text="Standard termination clause.")
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": True,
            "severity": "medium",
            "reasons": "Suspicious reasoning",
            "confidence": 0.8,
        }
        mock_llm.verify_anomaly = _mock_verify_rejected()

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
            count = await detect_anomalies_country_law(DOC_UUID)

        assert count == 0
        mock_session.add.assert_not_called()
        assert mock_llm.verify_anomaly.call_count == 1

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
            count = await detect_anomalies_country_law(DOC_UUID)

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
            await detect_anomalies_country_law(DOC_UUID)

        call_kwargs = mock_llm.detect_anomalies.call_args
        assert call_kwargs[1]["clause_type"] == "payment"
        assert call_kwargs[1]["standard_text"] == STANDARD_TEMPLATES["payment"]


class TestDetectAnomaliesReferenceDocs:
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
            count = await detect_anomalies_reference_docs(DOC_UUID, str(uuid.uuid4()))

        assert count == 0

    @pytest.mark.asyncio
    async def test_stores_matched_reference_with_3x_verify(self) -> None:
        clause = _make_clause(clause_type="termination", text="Immediate termination.")
        mock_llm = AsyncMock()
        mock_llm.detect_anomalies.return_value = {
            "is_anomaly": True,
            "severity": "high",
            "reasons": "Deviation from reference",
            "confidence": 0.88,
        }
        mock_llm.verify_anomaly = _mock_verify_verified()

        ref_chunks = [{"chunk_text": "Standard termination requires 30 days notice", "similarity": 0.85, "reference_document_name": "standard_template.pdf"}]

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
            patch("services.anomaly_detection_service.search_reference_chunks_batch", new_callable=AsyncMock, return_value=[ref_chunks]),
        ):
            count = await detect_anomalies_reference_docs(DOC_UUID, str(uuid.uuid4()))

        assert count == 1
        assert mock_llm.verify_anomaly.call_count == 3
        anomaly = mock_session.add.call_args[0][0]
        assert "Standard termination requires 30 days notice" in anomaly.matched_reference
        assert "standard_template.pdf" in anomaly.matched_reference
        assert anomaly.source == "reference_doc"

    @pytest.mark.asyncio
    async def test_skips_when_no_ref_chunks(self) -> None:
        clause = _make_clause(clause_type="termination", text="Immediate termination.")
        mock_llm = AsyncMock()

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
            patch("services.anomaly_detection_service.search_reference_chunks_batch", new_callable=AsyncMock, return_value=[[]]),
        ):
            count = await detect_anomalies_reference_docs(DOC_UUID, str(uuid.uuid4()))

        assert count == 0
        mock_llm.detect_anomalies.assert_not_called()


class TestStandardTemplates:
    def test_all_expected_types_present(self) -> None:
        expected = {"termination", "liability", "confidentiality", "payment", "dispute_resolution", "intellectual_property", "other"}
        assert set(STANDARD_TEMPLATES.keys()) == expected

    def test_other_template_is_empty(self) -> None:
        assert STANDARD_TEMPLATES["other"] == ""
