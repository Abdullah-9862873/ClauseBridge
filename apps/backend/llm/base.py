from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    Every provider (Groq, Anthropic, OpenAI) must implement
    these three methods.
    """

    @abstractmethod
    async def classify(self, text: str) -> dict[str, Any]:
        """Classify a document into a type (NDA, lease, contract, etc.)."""
        ...

    @abstractmethod
    async def extract_clauses(self, text: str) -> list[dict[str, Any]]:
        """Extract key clauses from a document."""
        ...

    @abstractmethod
    async def check_injection(self, text: str) -> bool:
        """Check if text contains a prompt injection attempt."""
        ...
    @abstractmethod
    async def detect_anomalies(self, clause_text: str, clause_type: str, standard_text: str) -> dict[str, Any]:
        """Compare a clause against a firm standard template.
        Returns: {"is_anomaly": bool, "severity": str, "reasons": str, "confidence": float}
        """
        ...
