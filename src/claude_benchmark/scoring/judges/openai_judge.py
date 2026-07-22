"""OpenAI judge provider — uses chat completions with JSON-schema structured output."""

from __future__ import annotations

import json
import os

from .base import JudgeError, JudgeProvider

DEFAULT_OPENAI_MODEL = "gpt-4o-2024-11-20"


def _wrap_schema_for_openai(schema: dict) -> dict:
    """Translate JUDGE_OUTPUT_SCHEMA into an OpenAI response_format payload.

    OpenAI's ``json_schema`` response format requires:
      - ``name`` (identifier, no spaces)
      - ``schema`` (the JSON schema body)
      - ``strict`` flag (recommended)
      - schemas with ``additionalProperties: false`` on every object
        when ``strict: true``
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "judge_evaluations",
            "schema": _enforce_strict(schema),
            "strict": True,
        },
    }


def _enforce_strict(schema: dict) -> dict:
    """Recursively add ``additionalProperties: false`` to all object schemas.

    Required by OpenAI's ``strict: true`` JSON-schema response format.
    """
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    if out.get("type") == "object":
        out.setdefault("additionalProperties", False)
        props = out.get("properties")
        if isinstance(props, dict):
            out["properties"] = {k: _enforce_strict(v) for k, v in props.items()}
    if out.get("type") == "array" and isinstance(out.get("items"), dict):
        out["items"] = _enforce_strict(out["items"])
    return out


class OpenAIJudge(JudgeProvider):
    """Judge backed by OpenAI chat completions with structured output."""

    provider = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model_id = model or DEFAULT_OPENAI_MODEL
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise JudgeError(
                "OpenAI judge requires OPENAI_API_KEY environment variable."
            )
        # Lazy client construction so import-time errors don't surface
        # for users who are only running the default Haiku path.
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - openai is in base deps
            raise JudgeError("openai package is not installed") from exc
        self._client = openai.OpenAI(api_key=self._api_key)

    def score(self, prompt: str, system: str, schema: dict) -> list[dict]:
        try:
            response = self._client.chat.completions.create(
                model=self.model_id,
                temperature=0,
                max_tokens=2048,
                response_format=_wrap_schema_for_openai(schema),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            raise JudgeError(f"OpenAI API call failed: {exc}") from exc

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            raise JudgeError("OpenAI judge returned no content")

        try:
            data = json.loads(choice.message.content)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"OpenAI judge returned non-JSON: {exc}") from exc

        evaluations = data.get("evaluations")
        if not isinstance(evaluations, list):
            raise JudgeError("OpenAI judge response missing 'evaluations' list")
        return evaluations
