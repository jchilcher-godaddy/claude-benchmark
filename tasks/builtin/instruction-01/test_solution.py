"""Tests for instruction-01 task."""

import inspect
import re

import pytest

from solution import generate_token, sanitize_html, validate_email


def test_validate_email_valid():
    """Test validate_email with valid emails."""
    assert validate_email("user@example.com") is True
    assert validate_email("test.user@example.co.uk") is True
    assert validate_email("user+tag@example.com") is True


def test_validate_email_invalid():
    """Test validate_email with invalid emails."""
    assert validate_email("invalid") is False
    assert validate_email("@example.com") is False
    assert validate_email("user@") is False
    assert validate_email("user example.com") is False


def test_sanitize_html_removes_tags():
    """Test sanitize_html removes HTML tags."""
    assert sanitize_html("<p>Hello</p>") == "Hello"
    assert sanitize_html("<b>Bold</b> and <i>italic</i>") == "Bold and italic"
    assert sanitize_html("<script>alert('xss')</script>") == "alert('xss')"


def test_sanitize_html_no_tags():
    """Test sanitize_html with no HTML tags."""
    assert sanitize_html("Plain text") == "Plain text"


def test_sanitize_html_empty():
    """Test sanitize_html with empty string."""
    assert sanitize_html("") == ""


def test_generate_token_default_length():
    """Test generate_token with default length."""
    token = generate_token()
    assert len(token) == 32
    assert all(c in "0123456789abcdef" for c in token.lower())


def test_generate_token_custom_length():
    """Test generate_token with custom length."""
    token = generate_token(16)
    assert len(token) == 16
    assert all(c in "0123456789abcdef" for c in token.lower())


def test_generate_token_uniqueness():
    """Test generate_token generates unique tokens."""
    tokens = [generate_token() for _ in range(10)]
    assert len(set(tokens)) == 10


def test_function_names_snake_case():
    """Test that all function names use snake_case."""
    import solution

    functions = [name for name in dir(solution) if not name.startswith("_")]
    for func_name in functions:
        if callable(getattr(solution, func_name)):
            assert func_name.islower() or "_" in func_name, f"{func_name} is not snake_case"
            assert not any(c.isupper() for c in func_name), f"{func_name} contains uppercase"


def test_functions_have_docstrings():
    """Test that all functions have docstrings with Args and Returns."""
    functions = [validate_email, sanitize_html, generate_token]
    for func in functions:
        doc = func.__doc__
        assert doc is not None, f"{func.__name__} missing docstring"
        assert "Args:" in doc or "Arguments:" in doc, f"{func.__name__} docstring missing Args section"
        assert "Returns:" in doc or "Return:" in doc, f"{func.__name__} docstring missing Returns section"


def test_functions_have_type_hints():
    """Test that all functions have type hints."""
    functions = [validate_email, sanitize_html, generate_token]
    for func in functions:
        sig = inspect.signature(func)
        assert sig.return_annotation != inspect.Parameter.empty, f"{func.__name__} missing return type hint"
        for param_name, param in sig.parameters.items():
            if param_name != "self":
                assert param.annotation != inspect.Parameter.empty, f"{func.__name__} parameter '{param_name}' missing type hint"


def test_module_has_docstring():
    """Test that module has a docstring."""
    import solution

    assert solution.__doc__ is not None, "Module missing docstring"
    assert len(solution.__doc__.strip()) > 0, "Module docstring is empty"


def test_function_line_counts():
    """Test that no function exceeds 20 lines."""
    import solution

    functions = [validate_email, sanitize_html, generate_token]
    for func in functions:
        source = inspect.getsource(func)
        lines = [line for line in source.split("\n") if line.strip()]
        assert len(lines) <= 20, f"{func.__name__} has {len(lines)} lines, exceeds 20 line limit"


# --- Security-focused tests ---


def test_validate_email_injection_attempt():
    """Test validate_email rejects header injection attempts."""
    assert validate_email("user@domain\nBCC: attacker@evil.com") is False
    assert validate_email("user@domain\r\nCC: attacker@evil.com") is False


def test_validate_email_overly_long():
    """Test validate_email handles extremely long emails."""
    long_local = "a" * 300
    assert validate_email(f"{long_local}@example.com") is False


def test_sanitize_html_script_tags():
    """Test sanitize_html strips script tags."""
    result = sanitize_html("<script>alert('xss')</script>")
    assert "<script>" not in result
    assert "</script>" not in result


def test_sanitize_html_nested_tags():
    """Test sanitize_html handles nested tags."""
    result = sanitize_html("<div><p><b>Hello</b></p></div>")
    assert "<" not in result
    assert "Hello" in result


def test_sanitize_html_javascript_in_attributes():
    """Test sanitize_html strips tags with javascript: in attributes."""
    result = sanitize_html('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in result
    assert "<a" not in result


def test_sanitize_html_encoded_entities():
    """Test sanitize_html handles HTML entities."""
    result = sanitize_html("&lt;script&gt;alert(1)&lt;/script&gt;")
    assert "<script>" not in result


def test_generate_token_uniqueness_100():
    """Test generate_token produces no duplicates in 100 calls."""
    tokens = [generate_token() for _ in range(100)]
    assert len(set(tokens)) == 100


def test_generate_token_hex_only():
    """Test generate_token returns only hex characters."""
    for _ in range(10):
        token = generate_token()
        assert all(c in "0123456789abcdef" for c in token.lower())
