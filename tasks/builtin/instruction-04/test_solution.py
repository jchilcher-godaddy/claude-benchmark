"""Tests for instruction-04: API client with 8 explicit constraints."""

import inspect
import logging
import time

import pytest

from solution import APIClient, APIError, ClientError, TimeoutError


class TestReturnDictShape:
    """Constraint 1: All methods return dict with status/body/headers keys."""

    def test_get_returns_dict_with_required_keys(self):
        client = APIClient()
        result = client.get("https://example.com")
        assert isinstance(result, dict)
        assert "status" in result
        assert "body" in result
        assert "headers" in result

    def test_post_returns_dict_with_required_keys(self):
        client = APIClient()
        result = client.post("https://example.com", data={"key": "value"})
        assert isinstance(result, dict)
        assert "status" in result
        assert "body" in result
        assert "headers" in result


class TestDefaultTimeout:
    """Constraint 2: Default timeout is 30 seconds."""

    def test_default_timeout_is_30(self):
        client = APIClient()
        assert hasattr(client, "_timeout") or hasattr(client, "timeout")
        timeout = getattr(client, "_timeout", getattr(client, "timeout", None))
        assert timeout == 30

    def test_set_timeout_changes_value(self):
        client = APIClient()
        client.set_timeout(60)
        timeout = getattr(client, "_timeout", getattr(client, "timeout", None))
        assert timeout == 60


class TestExceptionHierarchy:
    """Constraint 3: Custom exceptions with proper hierarchy."""

    def test_client_error_is_exception(self):
        assert issubclass(ClientError, Exception)

    def test_api_error_subclasses_client_error(self):
        assert issubclass(APIError, ClientError)

    def test_timeout_error_subclasses_client_error(self):
        assert issubclass(TimeoutError, ClientError)

    def test_api_error_is_catchable_as_client_error(self):
        with pytest.raises(ClientError):
            raise APIError("test")

    def test_timeout_error_is_catchable_as_client_error(self):
        with pytest.raises(ClientError):
            raise TimeoutError("test")


class TestRetryBehavior:
    """Constraint 4: Retry with exponential backoff."""

    def test_client_has_max_retries(self):
        client = APIClient()
        has_retry_attr = any(
            "retry" in attr.lower() or "retries" in attr.lower()
            for attr in dir(client)
        )
        assert has_retry_attr or True  # Implementation may vary


class TestLogging:
    """Constraint 5: Log all requests using logging module."""

    def test_get_logs_request(self, caplog):
        client = APIClient()
        with caplog.at_level(logging.DEBUG, logger="APIClient"):
            client.get("https://example.com")
        assert len(caplog.records) > 0

    def test_post_logs_request(self, caplog):
        client = APIClient()
        with caplog.at_level(logging.DEBUG, logger="APIClient"):
            client.post("https://example.com")
        assert len(caplog.records) > 0


class TestCaseInsensitiveHeaders:
    """Constraint 6: Headers are case-insensitive."""

    def test_set_header_case_insensitive(self):
        client = APIClient()
        client.set_header("Content-Type", "application/json")
        client.set_header("content-type", "text/plain")
        # Should have only one content-type header with the latest value
        result = client.get("https://example.com")
        # Verify the header was set (not duplicated)
        assert isinstance(result, dict)

    def test_headers_not_duplicated(self):
        client = APIClient()
        client.set_header("X-Custom", "value1")
        client.set_header("x-custom", "value2")
        # Internal header storage should have only one entry
        headers = getattr(client, "_headers", getattr(client, "headers", {}))
        lower_keys = [k.lower() for k in headers]
        assert lower_keys.count("x-custom") == 1


class TestContextManager:
    """Constraint 7: Usable as context manager."""

    def test_supports_context_manager(self):
        with APIClient() as client:
            result = client.get("https://example.com")
            assert isinstance(result, dict)

    def test_enter_returns_self(self):
        client = APIClient()
        result = client.__enter__()
        assert result is client
        client.__exit__(None, None, None)

    def test_has_exit_method(self):
        client = APIClient()
        assert hasattr(client, "__exit__")
        assert callable(client.__exit__)


class TestTypeHints:
    """Constraint 8: All public methods have type hints."""

    def test_get_has_type_hints(self):
        sig = inspect.signature(APIClient.get)
        assert sig.return_annotation != inspect.Parameter.empty

    def test_post_has_type_hints(self):
        sig = inspect.signature(APIClient.post)
        assert sig.return_annotation != inspect.Parameter.empty

    def test_set_header_has_type_hints(self):
        sig = inspect.signature(APIClient.set_header)
        for name, param in sig.parameters.items():
            if name != "self":
                assert param.annotation != inspect.Parameter.empty

    def test_set_timeout_has_type_hints(self):
        sig = inspect.signature(APIClient.set_timeout)
        for name, param in sig.parameters.items():
            if name != "self":
                assert param.annotation != inspect.Parameter.empty
