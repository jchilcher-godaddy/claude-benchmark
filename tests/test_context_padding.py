"""Tests for context_padding module."""

from __future__ import annotations

import pytest

from claude_benchmark.execution.context_padding import generate_padding


class TestGeneratePaddingBasic:
    """Basic functionality tests."""

    def test_returns_string(self):
        result = generate_padding(100)
        assert isinstance(result, str)

    def test_contains_begin_delimiter(self):
        result = generate_padding(100)
        assert "BEGIN BACKGROUND CONTEXT" in result

    def test_contains_end_delimiter(self):
        result = generate_padding(100)
        assert "END BACKGROUND CONTEXT" in result


class TestGeneratePaddingLength:
    """Length and token count tests."""

    def test_small_token_count(self):
        result = generate_padding(50)
        assert len(result) > 100

    def test_large_token_count(self):
        result = generate_padding(2000)
        assert len(result) > 5000

    def test_zero_tokens(self):
        result = generate_padding(0)
        assert "BEGIN BACKGROUND CONTEXT" in result
        assert "END BACKGROUND CONTEXT" in result


class TestGeneratePaddingStyles:
    """Style parameter tests."""

    def test_random_prose_produces_output(self):
        result = generate_padding(100, style="random_prose")
        assert len(result) > 0

    def test_code_comments_produces_output(self):
        result = generate_padding(100, style="code_comments")
        assert len(result) > 0

    def test_lorem_ipsum_produces_output(self):
        result = generate_padding(100, style="lorem_ipsum")
        assert len(result) > 0

    def test_mixed_produces_output(self):
        result = generate_padding(100, style="mixed")
        assert len(result) > 0

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError):
            generate_padding(100, style="invalid")


class TestGeneratePaddingDeterminism:
    """Determinism and reproducibility tests."""

    def test_same_inputs_same_output(self):
        result1 = generate_padding(100, style="random_prose")
        result2 = generate_padding(100, style="random_prose")
        assert result1 == result2

    def test_different_styles_differ(self):
        result1 = generate_padding(100, style="random_prose")
        result2 = generate_padding(100, style="lorem_ipsum")
        assert result1 != result2

    def test_different_token_counts_differ(self):
        result1 = generate_padding(100)
        result2 = generate_padding(500)
        assert len(result1) != len(result2)
