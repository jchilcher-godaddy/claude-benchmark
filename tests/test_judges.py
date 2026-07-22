"""Tests for the cross-family judge abstraction.

All tests mock the SDK clients — no real API calls are ever made.
The Gemini SDK is treated as optional: tests that exercise the Gemini
provider stub the import so the suite runs even when the package is
absent.
"""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.scoring.judges import JudgeError, get_judge
from claude_benchmark.scoring.judges.anthropic_judge import AnthropicJudge
from claude_benchmark.scoring.judges.openai_judge import (
    OpenAIJudge,
    _enforce_strict,
    _wrap_schema_for_openai,
)
from claude_benchmark.scoring.prompts import (
    JUDGE_OUTPUT_SCHEMA,
    JUDGE_SYSTEM_PROMPT,
)


_VALID_EVALUATIONS = [
    {"criterion": "code_readability", "score": 4, "reasoning": "Clean."},
    {"criterion": "architecture_quality", "score": 3, "reasoning": "OK."},
    {"criterion": "instruction_adherence", "score": 5, "reasoning": "Met."},
    {"criterion": "correctness_reasoning", "score": 4, "reasoning": "Correct."},
]


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    """Tests for ``get_judge`` spec resolution."""

    def test_haiku_returns_anthropic_judge(self):
        judge = get_judge("haiku")
        assert isinstance(judge, AnthropicJudge)
        assert judge.model_id == "haiku"
        assert judge.provider == "anthropic"

    def test_sonnet_returns_anthropic_judge(self):
        assert isinstance(get_judge("sonnet"), AnthropicJudge)

    def test_opus_returns_anthropic_judge(self):
        assert isinstance(get_judge("opus"), AnthropicJudge)

    def test_claude_model_id_returns_anthropic_judge(self):
        judge = get_judge("claude-haiku-4-5-20251001")
        assert isinstance(judge, AnthropicJudge)
        assert judge.model_id == "claude-haiku-4-5-20251001"

    def test_anthropic_prefix_returns_anthropic_judge(self):
        judge = get_judge("anthropic:claude-opus-4-7")
        assert isinstance(judge, AnthropicJudge)
        assert judge.model_id == "claude-opus-4-7"

    def test_gpt_4o_returns_openai_judge(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with patch("openai.OpenAI"):
            judge = get_judge("gpt-4o")
        assert isinstance(judge, OpenAIJudge)
        assert judge.model_id == "gpt-4o"
        assert judge.provider == "openai"

    def test_openai_prefix_returns_openai_judge(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with patch("openai.OpenAI"):
            judge = get_judge("openai:gpt-4o-2024-11-20")
        assert isinstance(judge, OpenAIJudge)
        assert judge.model_id == "gpt-4o-2024-11-20"

    def test_gpt_4_turbo_returns_openai_judge(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with patch("openai.OpenAI"):
            judge = get_judge("gpt-4-turbo")
        assert isinstance(judge, OpenAIJudge)

    def test_gemini_returns_gemini_judge(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        fake = _install_fake_genai(monkeypatch)
        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        judge = get_judge("gemini-2.5-pro")
        assert isinstance(judge, GeminiJudge)
        assert judge.model_id == "gemini-2.5-pro"
        assert judge.provider == "gemini"
        assert fake.configure.called

    def test_gemini_prefix_returns_gemini_judge(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        _install_fake_genai(monkeypatch)
        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        judge = get_judge("gemini:gemini-1.5-pro")
        assert isinstance(judge, GeminiJudge)
        assert judge.model_id == "gemini-1.5-pro"

    def test_unknown_spec_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown judge spec"):
            get_judge("llama-3.1")

    def test_unknown_provider_prefix_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown judge provider prefix"):
            get_judge("mistral:large")

    def test_empty_spec_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid judge spec"):
            get_judge("")


# ---------------------------------------------------------------------------
# AnthropicJudge tests
# ---------------------------------------------------------------------------


class TestAnthropicJudge:
    """The Anthropic judge wraps ``LLMJudgeScorer`` — verify delegation."""

    def test_score_delegates_to_llm_judge_scorer(self):
        judge = AnthropicJudge(model="haiku")
        with patch(
            "claude_benchmark.scoring.llm_judge.LLMJudgeScorer._select_call_fn"
        ) as mock_select:
            mock_call = MagicMock(
                return_value=json.dumps({"evaluations": _VALID_EVALUATIONS})
            )
            mock_select.return_value = mock_call

            evaluations = judge.score(
                prompt="user prompt",
                system=JUDGE_SYSTEM_PROMPT,
                schema=JUDGE_OUTPUT_SCHEMA,
            )

        assert evaluations == _VALID_EVALUATIONS
        mock_call.assert_called_once_with("user prompt")

    def test_score_raises_judge_error_on_non_json(self):
        judge = AnthropicJudge(model="haiku")
        with patch(
            "claude_benchmark.scoring.llm_judge.LLMJudgeScorer._select_call_fn"
        ) as mock_select:
            mock_select.return_value = MagicMock(return_value="not json")
            with pytest.raises(JudgeError, match="non-JSON"):
                judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)

    def test_score_raises_judge_error_on_missing_evaluations(self):
        judge = AnthropicJudge(model="haiku")
        with patch(
            "claude_benchmark.scoring.llm_judge.LLMJudgeScorer._select_call_fn"
        ) as mock_select:
            mock_select.return_value = MagicMock(
                return_value=json.dumps({"results": []})
            )
            with pytest.raises(JudgeError, match="missing 'evaluations'"):
                judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)


# ---------------------------------------------------------------------------
# OpenAIJudge tests
# ---------------------------------------------------------------------------


class TestOpenAIJudge:
    """OpenAI judge — mock the ``openai.OpenAI`` client."""

    def test_missing_api_key_raises_judge_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(JudgeError, match="OPENAI_API_KEY"):
            OpenAIJudge()

    def test_score_sends_expected_request(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_openai_response(
            {"evaluations": _VALID_EVALUATIONS}
        )
        with patch("openai.OpenAI", return_value=fake_client):
            judge = OpenAIJudge(model="gpt-4o-2024-11-20")
            evaluations = judge.score(
                prompt="user prompt",
                system=JUDGE_SYSTEM_PROMPT,
                schema=JUDGE_OUTPUT_SCHEMA,
            )

        assert evaluations == _VALID_EVALUATIONS
        call_kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-2024-11-20"
        assert call_kwargs["temperature"] == 0
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["strict"] is True
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == JUDGE_SYSTEM_PROMPT
        assert call_kwargs["messages"][1]["role"] == "user"
        assert call_kwargs["messages"][1]["content"] == "user prompt"

    def test_score_default_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with patch("openai.OpenAI"):
            judge = OpenAIJudge()
        assert judge.model_id == "gpt-4o-2024-11-20"

    def test_score_api_error_raises_judge_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("rate-limited")
        with patch("openai.OpenAI", return_value=fake_client):
            judge = OpenAIJudge()
            with pytest.raises(JudgeError, match="OpenAI API call failed"):
                judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)

    def test_score_non_json_raises_judge_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_openai_response(
            content="this is not json"
        )
        with patch("openai.OpenAI", return_value=fake_client):
            judge = OpenAIJudge()
            with pytest.raises(JudgeError, match="non-JSON"):
                judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)

    def test_score_missing_evaluations_raises_judge_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_openai_response(
            {"results": []}
        )
        with patch("openai.OpenAI", return_value=fake_client):
            judge = OpenAIJudge()
            with pytest.raises(JudgeError, match="missing 'evaluations'"):
                judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)

    def test_enforce_strict_adds_additional_properties_false(self):
        schema = {
            "type": "object",
            "properties": {
                "evaluations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"score": {"type": "integer"}},
                    },
                },
            },
        }
        out = _enforce_strict(schema)
        assert out["additionalProperties"] is False
        assert out["properties"]["evaluations"]["items"]["additionalProperties"] is False

    def test_wrap_schema_for_openai_shape(self):
        wrapped = _wrap_schema_for_openai(JUDGE_OUTPUT_SCHEMA)
        assert wrapped["type"] == "json_schema"
        assert wrapped["json_schema"]["name"] == "judge_evaluations"
        assert wrapped["json_schema"]["strict"] is True


# ---------------------------------------------------------------------------
# GeminiJudge tests
# ---------------------------------------------------------------------------


class TestGeminiJudge:
    """Gemini judge — mock the lazy ``google.generativeai`` import."""

    def test_missing_api_key_raises_judge_error(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        with pytest.raises(JudgeError, match="GOOGLE_API_KEY"):
            GeminiJudge()

    def test_missing_package_raises_judge_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        # Simulate the package being absent by purging it from sys.modules
        # and forcing the import to fail.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("google.generativeai") or name == "google":
                raise ImportError(f"No module named {name}")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        # Drop any cached import
        for mod in list(sys.modules):
            if mod.startswith("google"):
                monkeypatch.delitem(sys.modules, mod, raising=False)

        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        with pytest.raises(JudgeError, match="google-generativeai"):
            GeminiJudge()

    def test_score_sends_expected_request(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        fake_genai = _install_fake_genai(monkeypatch)
        # Configure the fake model to return a JSON response
        fake_response = types.SimpleNamespace(
            text=json.dumps({"evaluations": _VALID_EVALUATIONS})
        )
        fake_model = MagicMock()
        fake_model.generate_content.return_value = fake_response
        fake_genai.GenerativeModel.return_value = fake_model

        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        judge = GeminiJudge(model="gemini-2.5-pro")
        evaluations = judge.score(
            prompt="user prompt",
            system=JUDGE_SYSTEM_PROMPT,
            schema=JUDGE_OUTPUT_SCHEMA,
        )

        assert evaluations == _VALID_EVALUATIONS
        ctor_kwargs = fake_genai.GenerativeModel.call_args.kwargs
        assert ctor_kwargs["model_name"] == "gemini-2.5-pro"
        assert ctor_kwargs["system_instruction"] == JUDGE_SYSTEM_PROMPT
        assert ctor_kwargs["generation_config"]["response_mime_type"] == "application/json"
        assert ctor_kwargs["generation_config"]["temperature"] == 0
        assert "response_schema" in ctor_kwargs["generation_config"]
        fake_model.generate_content.assert_called_once_with("user prompt")

    def test_score_default_model(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        _install_fake_genai(monkeypatch)
        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        judge = GeminiJudge()
        assert judge.model_id == "gemini-2.5-pro"

    def test_score_api_error_raises_judge_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        fake_genai = _install_fake_genai(monkeypatch)
        fake_model = MagicMock()
        fake_model.generate_content.side_effect = RuntimeError("quota exceeded")
        fake_genai.GenerativeModel.return_value = fake_model

        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        judge = GeminiJudge()
        with pytest.raises(JudgeError, match="Gemini API call failed"):
            judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)

    def test_score_empty_response_raises_judge_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        fake_genai = _install_fake_genai(monkeypatch)
        fake_model = MagicMock()
        fake_model.generate_content.return_value = types.SimpleNamespace(text="")
        fake_genai.GenerativeModel.return_value = fake_model

        from claude_benchmark.scoring.judges.gemini_judge import GeminiJudge

        judge = GeminiJudge()
        with pytest.raises(JudgeError, match="no content"):
            judge.score("p", JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA)


# ---------------------------------------------------------------------------
# Integration with LLMJudgeScorer
# ---------------------------------------------------------------------------


class TestLLMJudgeScorerIntegration:
    """Verify ``LLMJudgeScorer`` honors the cross-family judge spec."""

    def test_default_keeps_legacy_anthropic_path(self):
        from claude_benchmark.scoring.llm_judge import LLMJudgeScorer

        scorer = LLMJudgeScorer()
        assert scorer.model == "haiku"
        assert scorer._provider is None  # legacy path

    def test_anthropic_spec_keeps_legacy_path(self):
        from claude_benchmark.scoring.llm_judge import LLMJudgeScorer

        scorer = LLMJudgeScorer(judge_model="sonnet")
        assert scorer.model == "sonnet"
        assert scorer._provider is None

    def test_openai_spec_routes_through_provider(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with patch("openai.OpenAI"):
            from claude_benchmark.scoring.llm_judge import LLMJudgeScorer

            scorer = LLMJudgeScorer(judge_model="gpt-4o")
        assert scorer._provider is not None
        assert scorer._provider.provider == "openai"

    def test_provider_score_is_recorded_on_llm_score(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_openai_response(
            {"evaluations": _VALID_EVALUATIONS}
        )
        with patch("openai.OpenAI", return_value=fake_client):
            from claude_benchmark.scoring.llm_judge import LLMJudgeScorer

            scorer = LLMJudgeScorer(judge_model="openai:gpt-4o-2024-11-20")
            score = scorer.judge_code(
                code="def x(): pass",
                task_description="Test",
            )

        assert score.judge_provider == "openai"
        assert score.judge_model_id == "gpt-4o-2024-11-20"
        # Default Anthropic path's judge_provider is recorded too
        dump = score.model_dump()
        assert dump["judge_provider"] == "openai"
        assert dump["judge_model_id"] == "gpt-4o-2024-11-20"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(payload: dict | None = None, content: str | None = None):
    """Build a minimal OpenAI-shaped chat-completions response."""
    if content is None:
        content = json.dumps(payload)
    message = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(choices=[choice])


def _install_fake_genai(monkeypatch) -> MagicMock:
    """Inject a fake ``google.generativeai`` module into ``sys.modules``.

    Returns the fake module so tests can configure it and assert on calls.
    """
    fake = MagicMock()
    fake.configure = MagicMock()
    fake.GenerativeModel = MagicMock()
    fake_google = types.ModuleType("google")
    fake_google.generativeai = fake
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    return fake
