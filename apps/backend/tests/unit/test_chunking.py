"""Unit tests for workers/chunking.py"""

from workers.chunking import _split_by_clauses, _split_paragraphs, split_into_chunks


class TestSplitParagraphs:
    def test_single_paragraph(self) -> None:
        assert _split_paragraphs("hello world") == ["hello world"]

    def test_double_newline_splits(self) -> None:
        text = "para one\n\npara two\n\npara three"
        result = _split_paragraphs(text)
        assert result == ["para one", "para two", "para three"]

    def test_empty_text(self) -> None:
        assert _split_paragraphs("") == []

    def test_whitespace_only(self) -> None:
        assert _split_paragraphs("   \n\n   ") == []

    def test_blank_lines_between(self) -> None:
        text = "first\n\n\n\nsecond"
        result = _split_paragraphs(text)
        assert result == ["first", "second"]


class TestSplitByClauses:
    def test_no_clause_pattern(self) -> None:
        text = "This is just a plain paragraph with no numbered clauses."
        result = _split_by_clauses(text)
        assert result == [text]

    def test_single_clause_pattern(self) -> None:
        text = "1. First clause text here."
        result = _split_by_clauses(text)
        # Only one match — not enough to split, returns the whole paragraph
        assert len(result) == 1

    def test_multiple_clause_pattern(self) -> None:
        text = (
            "1. First clause about termination.\n"
            "2. Second clause about liability.\n"
            "3. Third clause about payment."
        )
        result = _split_by_clauses(text)
        assert len(result) == 3
        assert "termination" in result[0]
        assert "liability" in result[1]
        assert "payment" in result[2]

    def test_section_prefix(self) -> None:
        text = (
            "Section 1 Confidentiality obligations.\n"
            "Section 2 Termination rights."
        )
        result = _split_by_clauses(text)
        assert len(result) == 2

    def test_article_prefix(self) -> None:
        text = (
            "Article I Definitions.\n"
            "Article II Obligations."
        )
        result = _split_by_clauses(text)
        assert len(result) == 2

    def test_parenthesized_numbers(self) -> None:
        text = (
            "(a) Sub-clause alpha.\n"
            "(b) Sub-clause beta."
        )
        result = _split_by_clauses(text)
        assert len(result) == 2

    def test_decimal_numbering(self) -> None:
        text = (
            "1.1 First sub-clause.\n"
            "1.2 Second sub-clause."
        )
        result = _split_by_clauses(text)
        assert len(result) == 2


class TestSplitIntoChunks:
    def test_full_paragraph_with_clauses(self) -> None:
        text = (
            "This agreement covers the following:\n\n"
            "1. Termination. Either party may terminate.\n"
            "2. Liability. Cap at fees paid.\n"
            "3. Payment. Due in 30 days."
        )
        result = split_into_chunks(text)
        assert len(result) >= 3

    def test_multiple_paragraphs(self) -> None:
        text = (
            "Intro paragraph about the agreement.\n\n"
            "1. First important clause.\n"
            "2. Second important clause."
        )
        result = split_into_chunks(text)
        assert len(result) >= 2

    def test_empty_text(self) -> None:
        assert split_into_chunks("") == []

    def test_plain_text_no_clauses(self) -> None:
        text = "Just a normal paragraph with no numbered items at all."
        result = split_into_chunks(text)
        assert len(result) == 1
        assert result[0] == text
