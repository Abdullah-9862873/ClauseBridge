import logging

from llm.groq_provider import GroqProvider

logger = logging.getLogger(__name__)
llm = GroqProvider()


async def check_injection(text: str) -> None:
    """Check for prompt injection attacks.
    Args:
        text: The text to check.
    Raises:
        ValueError: If a prompt injection attempt is detected.
    """
    is_injection = await llm.check_injection(text)
    if is_injection:
        logger.warning("Prompt injection detected in document text")
        raise ValueError("Prompt injection detected in document text")
