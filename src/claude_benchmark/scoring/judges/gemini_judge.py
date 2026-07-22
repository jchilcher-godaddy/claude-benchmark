"""Gemini judge provider — uses google-generativeai with response schema.

The ``google-generativeai`` package is an optional dependency. The import
is lazy (inside ``__init__``) so the default Haiku path doesn't require
the package to be installed.
"""

from __future__ import annotations

import json
import os

from .base import JudgeError, JudgeProvider

DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"


def _coerce_schema_for_gemini(schema: dict) -> dict:
    """Translate JUDGE_OUTPUT_SCHEMA into Gemini's response_schema format.

    Gemini accepts a subset of JSON Schema. The shared schema only uses
    ``type``, ``properties``, ``items``, and ``required``, which Gemini
    supports natively, so this is largely a passthrough. We strip
    ``additionalProperties`` if it ever sneaks in.
    """
    if not isinstance(schema, dict):
        return schema
    out = {k: v for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(out.get("properties"), dict):
        out["properties"] = {
            k: _coerce_schema_for_gemini(v) for k, v in out["properties"].items()
        }
    if isinstance(out.get("items"), dict):
        out["items"] = _coerce_schema_for_gemini(out["items"])
    return out


class GeminiJudge(JudgeProvider):
    """Judge backed by Google Gemini via ``google-generativeai``."""

    provider = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model_id = model or DEFAULT_GEMINI_MODEL
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self._api_key:
            raise JudgeError(
                "Gemini judge requires GOOGLE_API_KEY environment variable."
            )

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise JudgeError(
                "google-generativeai is not installed. "
                "Install with: pip install 'claude-benchmark[gemini]'"
            ) from exc

        genai.configure(api_key=self._api_key)
        self._genai = genai

    def score(self, prompt: str, system: str, schema: dict) -> list[dict]:
        gemini_schema = _coerce_schema_for_gemini(schema)
        generation_config = {
            "temperature": 0,
            "response_mime_type": "application/json",
            "response_schema": gemini_schema,
        }
        try:
            model = self._genai.GenerativeModel(
                model_name=self.model_id,
                system_instruction=system,
                generation_config=generation_config,
            )
            response = model.generate_content(prompt)
        except Exception as exc:
            raise JudgeError(f"Gemini API call failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise JudgeError("Gemini judge returned no content")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"Gemini judge returned non-JSON: {exc}") from exc

        evaluations = data.get("evaluations")
        if not isinstance(evaluations, list):
            raise JudgeError("Gemini judge response missing 'evaluations' list")
        return evaluations
