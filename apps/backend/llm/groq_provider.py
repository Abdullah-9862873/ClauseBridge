import json
import logging
import re
from pathlib import Path
from typing import Any

import groq

from cache.llm_cache import get_cached, set_cached
from core.config import settings
from llm.base import LLMProvider

PROMPTS_DIR = Path(__file__).parent / "prompts"
logger = logging.getLogger(__name__)


def _strip_markdown(text: str) -> str:
    """Strip markdown code block wrapping from LLM responses."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _strip_think_tags(text: str) -> str:
    """Strip thinking blocks from Qwen model responses."""
    pattern = r".*?</think>\n?"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


class GroqProvider(LLMProvider):
    """Groq LLM provider — free tier for development."""

    def __init__(self) -> None:
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.model = "qwen/qwen3.6-27b"

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt from the prompts directory."""
        return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

    async def classify(self, text: str) -> dict[str, Any]:
        """Classify a document into a type (NDA, lease, contract, etc.)."""
        cached = get_cached("classify", text[:2000])
        if cached:
            return cached  # type: ignore[return-value]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._load_prompt("classify_document.txt"),
                },
                {"role": "user", "content": text[:2000]},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        logger.info("classify raw response: %r", content[:200])
        try:
            result: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("classify JSON parse failed, using default")
            result = {"type": "other", "confidence": 0.0}
        set_cached("classify", text[:2000], result)
        return result

    async def extract_clauses(self, text: str) -> list[dict[str, Any]]:
        """Extract key clauses from a document."""
        cached = get_cached("extract", text[:2000])
        if cached:
            return cached  # type: ignore[return-value]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._load_prompt("extract_clauses.txt")},
                {"role": "user", "content": text[:2000]},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "[]"
        logger.info("extract_clauses raw response: %r", content[:200])
        try:
            result: list[dict[str, Any]] = json.loads(_strip_think_tags(_strip_markdown(content)))
        except json.JSONDecodeError:
            logger.warning("extract_clauses JSON parse failed, using default")
            result = []
        set_cached("extract", text[:2000], result)
        return result

    async def check_injection(self, text: str) -> bool:
        """Check if text contains a prompt injection attempt."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._load_prompt("injection_check.txt")},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content or "false"
        return content.strip().lower() == "true"
        
    async def detect_anomalies(
        self, clause_text: str, clause_type: str, standard_text: str
    ) -> dict[str, Any]:
        """Compare a clause against a firm standard template.
        Returns: {"is_anomaly": bool, "severity": str, "reasons": str, "confidence": float}
        """
        cached = get_cached("anomaly", clause_text[:2000] + standard_text[:2000])
        if cached:
            return cached  # type: ignore[return-value]
        prompt = self._load_prompt("detect_anomalies.txt")
        user_content = f"Clause type: {clause_type}\n\nExtracted clause:\n{clause_text}\n\nFirm standard template:\n{standard_text}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content or "{}"
        try:
            result: dict[str, Any] = json.loads(_strip_think_tags(_strip_markdown(content)))
        except json.JSONDecodeError:
            logger.warning("detect_anomalies JSON parse failed, using default")
            result = {"is_anomaly": False, "severity": "low", "reasons": "", "confidence": 0.0}
        set_cached("anomaly", clause_text[:2000] + standard_text[:2000], result)
        return result
