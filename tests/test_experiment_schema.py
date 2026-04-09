"""Tests for experiment schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from claude_benchmark.experiments.schema import (
    ExperimentConfig,
    ExperimentDefaults,
    VariantConfig,
)


class TestVariantConfig:
    """Tests for VariantConfig model."""

    def test_minimal(self):
        config = VariantConfig(label="x")
        assert config.label == "x"
        assert config.prompt_prefix is None
        assert config.system_prompt_extra is None
        assert config.temperature is None

    def test_full(self):
        config = VariantConfig(
            label="test",
            prompt_prefix="prefix",
            system_prompt_extra="extra",
            temperature=0.7,
        )
        assert config.label == "test"
        assert config.prompt_prefix == "prefix"
        assert config.system_prompt_extra == "extra"
        assert config.temperature == 0.7

    def test_padding_tokens(self):
        config = VariantConfig(label="padded", padding_tokens=2000)
        assert config.padding_tokens == 2000

    def test_padding_tokens_default_none(self):
        config = VariantConfig(label="clean")
        assert config.padding_tokens is None

    def test_models_override(self):
        config = VariantConfig(label="multi", models=["haiku", "opus"])
        assert config.models == ["haiku", "opus"]

    def test_models_default_none(self):
        config = VariantConfig(label="default")
        assert config.models is None

    def test_missing_label_raises(self):
        with pytest.raises(ValidationError):
            VariantConfig()


class TestExperimentDefaults:
    """Tests for ExperimentDefaults model."""

    def test_defaults_populated(self):
        defaults = ExperimentDefaults()
        assert defaults.models == ["sonnet"]
        assert defaults.profiles == ["empty"]
        assert defaults.reps == 10

    def test_custom_overrides(self):
        defaults = ExperimentDefaults(reps=5, models=["haiku"])
        assert defaults.reps == 5
        assert defaults.models == ["haiku"]


class TestExperimentConfig:
    """Tests for ExperimentConfig model."""

    def test_minimal_valid(self):
        config = ExperimentConfig(
            name="x",
            variants=[VariantConfig(label="a")],
        )
        assert config.name == "x"
        assert len(config.variants) == 1

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ExperimentConfig(variants=[VariantConfig(label="a")])

    def test_missing_variants_raises(self):
        with pytest.raises(ValidationError):
            ExperimentConfig(name="x")
