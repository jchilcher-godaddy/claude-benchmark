import hashlib
from datetime import datetime
from urllib.parse import urlparse


class URLShortener:
    """URL shortener with validation, stats tracking, and security checks."""

    DANGEROUS_SCHEMES = {"javascript", "data", "vbscript"}

    def __init__(self):
        self._url_to_code = {}
        self._code_to_entry = {}

    def _validate_url(self, url):
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: missing scheme or host: {url!r}")
        if parsed.scheme.lower() in self.DANGEROUS_SCHEMES:
            raise ValueError(f"Dangerous URL scheme: {parsed.scheme!r}")

    def _generate_code(self, url, attempt=0):
        data = f"{url}:{attempt}"
        return hashlib.sha256(data.encode()).hexdigest()[:8]

    def shorten(self, url):
        self._validate_url(url)
        if url in self._url_to_code:
            return self._url_to_code[url]

        attempt = 0
        code = self._generate_code(url, attempt)
        while code in self._code_to_entry:
            attempt += 1
            code = self._generate_code(url, attempt)

        self._code_to_entry[code] = {
            "original_url": url,
            "click_count": 0,
            "created_at": datetime.now(),
        }
        self._url_to_code[url] = code
        return code

    def resolve(self, short_code):
        if short_code not in self._code_to_entry:
            raise KeyError(f"Short code not found: {short_code!r}")
        self._code_to_entry[short_code]["click_count"] += 1
        return self._code_to_entry[short_code]["original_url"]

    def get_stats(self, short_code):
        if short_code not in self._code_to_entry:
            raise KeyError(f"Short code not found: {short_code!r}")
        entry = self._code_to_entry[short_code]
        return {
            "original_url": entry["original_url"],
            "click_count": entry["click_count"],
            "created_at": entry["created_at"],
        }

    def delete(self, short_code):
        if short_code not in self._code_to_entry:
            return False
        url = self._code_to_entry[short_code]["original_url"]
        del self._code_to_entry[short_code]
        self._url_to_code.pop(url, None)
        return True
