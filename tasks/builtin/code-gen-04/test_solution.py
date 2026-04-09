"""Tests for code-gen-04: URL shortener service."""

from datetime import datetime

import pytest

from url_shortener import URLShortener


class TestShortenAndResolve:
    def test_shorten_returns_code(self):
        s = URLShortener()
        code = s.shorten("https://example.com")
        assert isinstance(code, str)
        assert len(code) >= 6

    def test_resolve_returns_original(self):
        s = URLShortener()
        code = s.shorten("https://example.com")
        assert s.resolve(code) == "https://example.com"

    def test_shorten_same_url_returns_same_code(self):
        s = URLShortener()
        code1 = s.shorten("https://example.com")
        code2 = s.shorten("https://example.com")
        assert code1 == code2

    def test_shorten_different_urls_return_different_codes(self):
        s = URLShortener()
        code1 = s.shorten("https://example.com")
        code2 = s.shorten("https://other.com")
        assert code1 != code2

    def test_resolve_nonexistent_raises(self):
        s = URLShortener()
        with pytest.raises(KeyError):
            s.resolve("nonexistent")


class TestURLValidation:
    def test_rejects_no_scheme(self):
        s = URLShortener()
        with pytest.raises(ValueError):
            s.shorten("example.com")

    def test_rejects_no_host(self):
        s = URLShortener()
        with pytest.raises(ValueError):
            s.shorten("https://")

    def test_rejects_empty_string(self):
        s = URLShortener()
        with pytest.raises(ValueError):
            s.shorten("")

    def test_rejects_none(self):
        s = URLShortener()
        with pytest.raises((ValueError, TypeError)):
            s.shorten(None)


class TestDangerousSchemes:
    def test_rejects_javascript_scheme(self):
        s = URLShortener()
        with pytest.raises(ValueError, match="[Dd]angerous|[Ss]cheme|javascript"):
            s.shorten("javascript:alert('xss')")

    def test_rejects_data_scheme(self):
        s = URLShortener()
        with pytest.raises(ValueError):
            s.shorten("data:text/html,<script>alert(1)</script>")

    def test_rejects_vbscript_scheme(self):
        s = URLShortener()
        with pytest.raises(ValueError):
            s.shorten("vbscript:MsgBox")


class TestStats:
    def test_stats_initial(self):
        s = URLShortener()
        code = s.shorten("https://example.com")
        stats = s.get_stats(code)
        assert stats["original_url"] == "https://example.com"
        assert stats["click_count"] == 0
        assert isinstance(stats["created_at"], datetime)

    def test_stats_after_resolves(self):
        s = URLShortener()
        code = s.shorten("https://example.com")
        s.resolve(code)
        s.resolve(code)
        s.resolve(code)
        stats = s.get_stats(code)
        assert stats["click_count"] == 3

    def test_stats_nonexistent_raises(self):
        s = URLShortener()
        with pytest.raises(KeyError):
            s.get_stats("nonexistent")


class TestDelete:
    def test_delete_existing(self):
        s = URLShortener()
        code = s.shorten("https://example.com")
        assert s.delete(code) is True

    def test_delete_nonexistent(self):
        s = URLShortener()
        assert s.delete("nonexistent") is False

    def test_resolve_after_delete_raises(self):
        s = URLShortener()
        code = s.shorten("https://example.com")
        s.delete(code)
        with pytest.raises(KeyError):
            s.resolve(code)
