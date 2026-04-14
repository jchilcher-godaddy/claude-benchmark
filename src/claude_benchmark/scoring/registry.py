"""Scorer registry for mapping languages to their static analysis implementations."""

from __future__ import annotations

from claude_benchmark.tasks.schema import Language

from .base_scorer import BaseStaticScorer
from .models import ScoringWeights

_REGISTRY: dict[Language, type[BaseStaticScorer]] = {}


def register_scorer(language: Language, scorer_cls: type[BaseStaticScorer]) -> None:
    """Register a static scorer class for a language."""
    _REGISTRY[language] = scorer_cls


def get_scorer(language: Language, weights: ScoringWeights | None = None) -> BaseStaticScorer:
    """Get a scorer instance for the given language.

    Raises:
        ValueError: If no scorer is registered for the language.
    """
    scorer_cls = _REGISTRY.get(language)
    if scorer_cls is None:
        registered = ", ".join(lang.value for lang in _REGISTRY)
        raise ValueError(
            f"No static scorer registered for language '{language.value}'. "
            f"Registered languages: {registered or 'none'}"
        )
    return scorer_cls(weights=weights)


def registered_languages() -> list[Language]:
    """Return list of languages with registered scorers."""
    return list(_REGISTRY.keys())


# Register all scorers at import time
def _register_defaults() -> None:
    from .static import PythonStaticScorer
    register_scorer(Language.PYTHON, PythonStaticScorer)

    from .lang_go import GoStaticScorer
    register_scorer(Language.GO, GoStaticScorer)

    from .lang_javascript import JavaScriptStaticScorer
    register_scorer(Language.JAVASCRIPT, JavaScriptStaticScorer)

    from .lang_csharp import CSharpStaticScorer
    register_scorer(Language.CSHARP, CSharpStaticScorer)


_register_defaults()
