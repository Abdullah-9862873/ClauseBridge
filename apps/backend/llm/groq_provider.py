import asyncio
import json
import logging
import re
import time
from pathlib import Path
from string import Template
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
    pattern = r"<think>.*?</think>\n?"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


async def _make_llm_call(
    self: "GroqProvider", model: str, messages: list[dict], temperature: float, max_tokens: int
) -> str:
    """Make an LLM API call with rate limiting."""
    start = time.monotonic()
    try:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or "{}"
        elapsed = time.monotonic() - start
        logger.info(
            "LLM API call took %.2fs (model=%s, max_tokens=%d)",
            elapsed,
            model,
            max_tokens,
        )
        return content
    except groq.RateLimitError as e:
        elapsed = time.monotonic() - start
        logger.warning(
            "LLM API rate limited after %.2fs, retrying in 2s (error: %s)",
            elapsed,
            str(e),
        )
        await asyncio.sleep(2)
        return await _make_llm_call(self, model, messages, temperature, max_tokens)
    except groq.BadRequestError:
        logger.warning("LLM API 400 error")
        return "{}"


class GroqProvider(LLMProvider):
    """Groq LLM provider — free tier for development."""

    def __init__(self) -> None:
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.model = "openai/gpt-oss-120b"

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt from the prompts directory."""
        return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

    async def classify(self, text: str) -> dict[str, Any]:
        """Classify a document into a type (NDA, lease, contract, etc.)."""
        cached = get_cached("classify", text[:2000])
        if cached:
            return cached  # type: ignore[return-value]
        content = await _make_llm_call(
            self,
            self.model,
            [
                {
                    "role": "system",
                    "content": self._load_prompt("classify_document.txt"),
                },
                {"role": "user", "content": text[:2000]},
            ],
            temperature=0.0,
            max_tokens=512,
        )
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
        cache_key = text[:2000]
        cached = get_cached("extract", cache_key)
        if cached:
            return cached  # type: ignore[return-value]
        for attempt in range(2):
            content = await _make_llm_call(
                self,
                self.model,
                [
                    {"role": "system", "content": self._load_prompt("extract_clauses.txt")},
                    {"role": "user", "content": text[:2000]},
                ],
                temperature=0.0 if attempt == 0 else 0.2,
                max_tokens=2048,
            )
            logger.info("extract_clauses raw response length: %d (attempt %d)", len(content), attempt + 1)
            cleaned = _strip_think_tags(_strip_markdown(content))
            logger.info("extract_clauses cleaned response length: %d", len(cleaned))
            try:
                result: list[dict[str, Any]] = json.loads(cleaned)
                if result:
                    break
                logger.warning("extract_clauses returned empty array, retrying")
            except json.JSONDecodeError:
                logger.warning("extract_clauses JSON parse failed (attempt %d): %s", attempt + 1, cleaned[:300])
                result = []
        set_cached("extract", cache_key, result)
        return result

    async def check_injection(self, text: str) -> bool:
        """Check if text contains a prompt injection attempt."""
        try:
            content = await _make_llm_call(
                self,
                self.model,
                [
                    {"role": "system", "content": self._load_prompt("injection_check.txt")},
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            return content.strip().lower() == "true"
        except groq.RateLimitError:
            logger.warning("check_injection rate limited, skipping — assuming no injection")
            return False

    async def detect_anomalies(
        self,
        clause_text: str,
        clause_type: str,
        standard_text: str,
        country_code: str | None = None,
        reference_context: str | None = None,
    ) -> dict[str, Any]:
        """Compare a clause against the relevant country's laws using LLM's legal knowledge.
        Returns: {"is_anomaly": bool, "severity": str, "reasons": str, "confidence": float,
                  "applicable_law": str, "document_type": str}
        """
        cache_key = f"{clause_text[:2000]}{standard_text[:2000]}{country_code or ''}{reference_context[:2000] if reference_context else ''}"
        default = {
            "is_anomaly": False,
            "severity": "low",
            "reasons": "",
            "confidence": 0.0,
            "applicable_law": "",
            "document_type": "",
        }
        try:
            if country_code:
                raw = self._load_prompt("detect_anomalies_country.txt")
                prompt = Template(raw).safe_substitute(
                    country_code=country_code,
                    standard_text=standard_text or "(none provided)",
                )
                user_content = (
                    f"Document type context: {clause_type}\n\n"
                    f"Full document/clause text:\n{clause_text}\n\n"
                    f"Analyze this document for legal anomalies, cross-paragraph contradictions, "
                    f"and violations of {country_code} law."
                )
            else:
                prompt = self._load_prompt("detect_anomalies.txt")
                user_content = (
                    f"Clause type: {clause_type}\n\n"
                    f"Extracted clause:\n{clause_text}\n\n"
                    f"Firm standard template:\n{standard_text}"
                )

            # Add reference context if available (Layer 1)
            if reference_context:
                user_content += (
                    "\n\n--- Reference Documents (from uploaded legal references) ---\n"
                    f"{reference_context}\n"
                    "--- End Reference Documents ---\n\n"
                    "IMPORTANT: The above reference documents are from the user's uploaded legal materials. "
                    "Check this clause against them first. If it conflicts with or deviates from these references, "
                    "flag it as an anomaly with HIGH priority. Cite the specific reference in your reasons."
                )
            content = await _make_llm_call(
                self,
                self.model,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                max_tokens=2048,
            )
            cleaned = _strip_think_tags(_strip_markdown(content))
            try:
                result: dict[str, Any] = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("detect_anomalies JSON parse failed: %s", cleaned[:300])
                result = default
        except groq.RateLimitError as e:
            logger.warning("detect_anomalies rate limited after %.2fs, using default: %s", time.monotonic() - e.__traceback__.tb_frame.f_locals.get('_start', 0), str(e))
            result = default
        set_cached("anomaly", cache_key, result)
        return result

    async def analyze_full_document(
        self,
        full_text: str,
        country_code: str,
    ) -> dict[str, Any]:
        """Analyze the COMPLETE document text for legal anomalies.
        This is the most powerful analysis mode — it sees the entire document
        at once and can detect cross-paragraph contradictions and violations
        of the country's laws that span multiple sections.

        Returns: {"is_anomaly": bool, "severity": str, "reasons": str, "confidence": float,
                  "applicable_law": str, "document_type": str, "violations": list}
        """
        cache_key = f"full_doc:{full_text[:2000]}{country_code}"
        default = {
            "is_anomaly": False,
            "severity": "low",
            "reasons": "",
            "confidence": 0.0,
            "applicable_law": "",
            "document_type": "",
            "violations": [],
        }

        try:
            # Use a focused prompt for full-document analysis
            system_prompt = f"""You are an expert legal analyst with deep knowledge of {country_code} law. Your job is to analyze a COMPLETE legal document and identify any violations of the law.

Focus on:
1. **Cross-paragraph contradictions**: Facts stated in one paragraph that contradict other paragraphs
2. **Legal compliance**: Claims, distributions, or positions that violate {country_code} law
3. **Exclusion of legal heirs**: For inheritance/family matters, identify if legal heirs are being excluded
4. **Incorrect legal procedures**: Steps taken that don't follow the law

For {country_code} inheritance/family law matters, recall:
- Pakistan (PK): Muslim Family Laws Ordinance 1961, Islamic Sharia inheritance, parents ARE legal heirs, specific share rules
- India (IN): Hindu Succession Act 1956, Muslim Personal Law, parents ARE legal heirs
- UK/US: Intestacy laws, parents may or may not be heirs depending on jurisdiction

Return ONLY valid JSON:
{{
  "is_anomaly": boolean,
  "severity": "high" | "medium" | "low" | "none",
  "reasons": "Detailed explanation of what the law states, what the document says, and why they conflict",
  "confidence": float 0-1,
  "applicable_law": "specific law name",
  "document_type": "type of legal matter",
  "violations": ["list of specific violations found"]
}}

Be thorough. If parents are mentioned as alive but excluded from inheritance, this is a CLEAR VIOLATION of Islamic inheritance law in Pakistan. Flag it with high confidence (0.8-0.95)."""

            user_content = f"""Analyze this COMPLETE legal document from {country_code}:

{full_text}

Identify ALL legal violations, cross-paragraph contradictions, and compliance issues."""

            content = await _make_llm_call(
                self,
                self.model,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                max_tokens=3000,
            )

            cleaned = _strip_think_tags(_strip_markdown(content))
            logger.info("full document analysis response: %s", cleaned[:500])

            try:
                result: dict[str, Any] = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("analyze_full_document JSON parse failed: %s", cleaned[:300])
                result = default

        except groq.RateLimitError as e:
            logger.warning("analyze_full_document rate limited: %s", str(e))
            result = default

        set_cached("anomaly", cache_key, result)
        return result

    async def verify_anomaly(
        self,
        clause_text: str,
        clause_type: str,
        severity: str,
        reasons: str,
        source: str,
        matched_reference: str | None = None,
    ) -> dict[str, Any]:
        """Verify an anomaly detection result for hallucination.
        Returns: {"verified": bool, "confidence_adjustment": float}
        """
        cache_key = f"verify:{clause_text[:500]}{reasons[:500]}{source}"
        cached = get_cached("verify", cache_key)
        if cached:
            return cached  # type: ignore[return-value]
        default = {"verified": False, "confidence_adjustment": 0.0}
        try:
            prompt = self._load_prompt("verify_anomaly.txt")
            user_content = (
                f"Clause type: {clause_type}\n\n"
                f"Extracted clause:\n{clause_text}\n\n"
                f"Detected anomaly:\n"
                f"- Severity: {severity}\n"
                f"- Reasoning: {reasons}\n"
                f"- Source: {source}\n"
            )
            if matched_reference:
                user_content += f"\nMatched reference document:\n{matched_reference}\n"

            content = await _make_llm_call(
                self,
                self.model,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                max_tokens=512,
            )
            cleaned = _strip_think_tags(_strip_markdown(content))
            try:
                result: dict[str, Any] = json.loads(cleaned)
                # Clamp confidence_adjustment to [-0.3, 0.3]
                adj = result.get("confidence_adjustment", 0.0)
                result["confidence_adjustment"] = max(-0.3, min(0.3, adj))
            except json.JSONDecodeError:
                logger.warning("verify_anomaly JSON parse failed: %s", cleaned[:300])
                result = default
        except groq.RateLimitError:
            logger.warning("verify_anomaly rate limited, using default")
            result = default
        set_cached("verify", cache_key, result)
        return result