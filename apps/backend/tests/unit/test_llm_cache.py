"""Unit tests for cache/llm_cache.py"""

from __future__ import annotations

import json
from unittest.mock import patch

from cache.llm_cache import _make_key, delete_clause_cache, delete_document_cache, get_cached, set_cached


class TestMakeKey:
    def test_key_format(self) -> None:
        key = _make_key("classify", "hello world")
        assert key.startswith("llm:classify:")
        assert len(key) == len("llm:classify:") + 16  # sha256[:16]

    def test_same_inputs_same_key(self) -> None:
        k1 = _make_key("extract", "some text")
        k2 = _make_key("extract", "some text")
        assert k1 == k2

    def test_different_methods_different_keys(self) -> None:
        k1 = _make_key("classify", "text")
        k2 = _make_key("extract", "text")
        assert k1 != k2

    def test_different_text_different_keys(self) -> None:
        k1 = _make_key("classify", "text A")
        k2 = _make_key("classify", "text B")
        assert k1 != k2


class TestCacheOperations:
    def test_set_then_get(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            set_cached("classify", "test text", {"type": "NDA", "confidence": 0.9})
            result = get_cached("classify", "test text")
            assert result == {"type": "NDA", "confidence": 0.9}

    def test_cache_miss(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            result = get_cached("classify", "nonexistent text")
            assert result is None

    def test_cache_returns_list(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            clauses = [{"clause_type": "termination", "text": "clause text"}]
            set_cached("extract", "doc text", clauses)
            result = get_cached("extract", "doc text")
            assert result == clauses

    def test_different_methods_independent(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            set_cached("classify", "text", {"type": "NDA"})
            set_cached("extract", "text", [{"clause_type": "other"}])
            assert get_cached("classify", "text") == {"type": "NDA"}
            assert get_cached("extract", "text") == [{"clause_type": "other"}]


class TestDeleteDocumentCache:
    def test_deletes_classify_and_extract(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            set_cached("classify", "doc text", {"type": "NDA"})
            set_cached("extract", "doc text", [{"text": "clause"}])
            deleted = delete_document_cache("doc text")
            assert deleted == 2
            assert get_cached("classify", "doc text") is None
            assert get_cached("extract", "doc text") is None

    def test_returns_zero_when_empty(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            deleted = delete_document_cache("nonexistent")
            assert deleted == 0


class TestDeleteClauseCache:
    def test_deletes_anomaly_cache(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            set_cached("anomaly", "clause text" + "standard text", {"is_anomaly": True})
            deleted = delete_clause_cache("clause text", "standard text")
            assert deleted == 1

    def test_returns_zero_when_no_match(self, fake_redis) -> None:
        with patch("cache.llm_cache._redis", fake_redis):
            deleted = delete_clause_cache("no match", "standard")
            assert deleted == 0
