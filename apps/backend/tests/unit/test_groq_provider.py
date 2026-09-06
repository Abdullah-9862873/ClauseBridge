"""Unit tests for llm/groq_provider.py (mocked LLM calls)"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from llm.groq_provider import GroqProvider, _strip_markdown, _strip_think_tags


class TestStripMarkdown:
    def test_strips_json_code_block(self) -> None:
        text = '```json\n{"type": "NDA"}\n```'
        assert _strip_markdown(text) == '{"type": "NDA"}'

    def test_strips_plain_code_block(self) -> None:
        text = '```\n{"key": "value"}\n```'
        assert _strip_markdown(text) == '{"key": "value"}'

    def test_no_code_block(self) -> None:
        text = '{"type": "NDA"}'
        assert _strip_markdown(text) == '{"type": "NDA"}'

    def test_multiline_json(self) -> None:
        text = '```json\n{"type": "NDA",\n"confidence": 0.9}\n```'
        result = _strip_markdown(text)
        parsed = json.loads(result)
        assert parsed["type"] == "NDA"

    def test_empty_string(self) -> None:
        assert _strip_markdown("") == ""


class TestStripThinkTags:
    def test_removes_think_block(self) -> None:
        text = '<think>thinking</think>\n{"result": "ok"}'
        result = _strip_think_tags(text)
        assert "<think>" not in result
        assert "</think>" not in result
        assert '{"result": "ok"}' in result

    def test_no_think_block(self) -> None:
        text = '{"result": "ok"}'
        assert _strip_think_tags(text) == text

    def test_multiple_think_blocks(self) -> None:
        text = '<think>thinking1</think> real content <think>thinking2</think>'
        result = _strip_think_tags(text)
        assert "<think>" not in result
        assert "real content" in result

    def test_empty_string(self) -> None:
        assert _strip_think_tags("") == ""


class TestGroqProvider:
    def test_init_sets_model(self) -> None:
        with patch("llm.groq_provider.groq"):
            provider = GroqProvider()
            assert provider.model == "openai/gpt-oss-120b"

    def test_load_prompt(self) -> None:
        with patch("llm.groq_provider.groq"):
            provider = GroqProvider()
            prompt = provider._load_prompt("classify_document.txt")
            assert "classifier" in prompt.lower() or "classify" in prompt.lower()
