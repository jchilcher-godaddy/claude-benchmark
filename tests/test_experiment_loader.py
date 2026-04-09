"""Tests for experiment configuration loading and expansion."""

import tomllib
from pathlib import Path

import pytest
import tomli_w
from pydantic import ValidationError

from claude_benchmark.execution.parallel import BenchmarkRun
from claude_benchmark.experiments.loader import expand_experiment, load_experiment
from claude_benchmark.experiments.schema import (
    ExperimentConfig,
    ExperimentDefaults,
    VariantConfig,
)


class TestLoadExperiment:
    """Tests for load_experiment function."""

    def test_valid_toml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "experiment.toml"
        config_data = {
            "name": "test-experiment",
            "defaults": {
                "tasks": ["t1"],
                "models": ["sonnet"],
                "profiles": ["empty"],
                "reps": 2,
            },
            "variants": [
                {"label": "control"},
                {"label": "treatment", "prompt_prefix": "Please "},
            ],
        }
        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        config = load_experiment(config_path)

        assert config.name == "test-experiment"
        assert len(config.variants) == 2
        assert config.variants[0].label == "control"
        assert config.variants[1].label == "treatment"

    def test_file_not_found(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.toml"

        with pytest.raises(FileNotFoundError):
            load_experiment(nonexistent)

    def test_invalid_toml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "invalid.toml"
        config_path.write_text("this is [not valid toml")

        with pytest.raises(tomllib.TOMLDecodeError):
            load_experiment(config_path)

    def test_invalid_schema(self, tmp_path: Path) -> None:
        config_path = tmp_path / "invalid_schema.toml"
        config_data = {
            "description": "missing required name field",
            "variants": [{"label": "v1"}],
        }
        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        with pytest.raises(ValidationError):
            load_experiment(config_path)


class TestExpandExperiment:
    """Tests for expand_experiment function."""

    def test_cartesian_product_size(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=2,
            ),
            variants=[VariantConfig(label="v1"), VariantConfig(label="v2")],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert len(runs) == 4

    def test_variant_label_set(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[VariantConfig(label="v1"), VariantConfig(label="v2")],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].variant_label == "v1"
        assert runs[1].variant_label == "v2"

    def test_system_prompt_extra_wired(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[
                VariantConfig(
                    label="v1", system_prompt_extra="You are a helpful assistant."
                )
            ],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].system_prompt_extra == "You are a helpful assistant."

    def test_prompt_prefix_wired(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[VariantConfig(label="v1", prompt_prefix="Please ")],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].prompt_prefix == "Please "

    def test_temperature_cascade_variant_overrides_default(
        self, tmp_path: Path
    ) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
                temperature=0.5,
            ),
            variants=[VariantConfig(label="v1", temperature=0.9)],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].temperature == 0.9

    def test_temperature_cascade_default_used(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
                temperature=0.5,
            ),
            variants=[VariantConfig(label="v1", temperature=None)],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].temperature == 0.5

    def test_temperature_both_none(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
                temperature=None,
            ),
            variants=[VariantConfig(label="v1", temperature=None)],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].temperature is None

    def test_missing_task_raises(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["nonexistent_task"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[VariantConfig(label="v1")],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        with pytest.raises(ValueError, match="not found"):
            expand_experiment(config, task_dirs, profile_paths, tmp_path / "results")

    def test_padding_tokens_produces_expanded_prefix(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[
                VariantConfig(label="clean"),
                VariantConfig(label="padded", padding_tokens=500),
            ],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        clean_run = [r for r in runs if r.variant_label == "clean"][0]
        padded_run = [r for r in runs if r.variant_label == "padded"][0]

        assert clean_run.prompt_prefix is None
        assert padded_run.prompt_prefix is not None
        assert "BEGIN BACKGROUND CONTEXT" in padded_run.prompt_prefix
        assert len(padded_run.prompt_prefix) > 100

    def test_padding_tokens_combined_with_prompt_prefix(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[
                VariantConfig(label="both", padding_tokens=500, prompt_prefix="Extra: "),
            ],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert runs[0].prompt_prefix is not None
        assert runs[0].prompt_prefix.endswith("Extra: ")
        assert "BEGIN BACKGROUND CONTEXT" in runs[0].prompt_prefix

    def test_variant_models_override(self, tmp_path: Path) -> None:
        """Variant-level models override defaults.models."""
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[
                VariantConfig(label="default-model"),
                VariantConfig(label="multi-model", models=["haiku", "opus"]),
            ],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        # default-model variant: 1 model x 1 rep = 1 run
        # multi-model variant: 2 models x 1 rep = 2 runs
        assert len(runs) == 3

        default_runs = [r for r in runs if r.variant_label == "default-model"]
        assert len(default_runs) == 1
        assert default_runs[0].model == "sonnet"

        multi_runs = [r for r in runs if r.variant_label == "multi-model"]
        assert len(multi_runs) == 2
        assert {r.model for r in multi_runs} == {"haiku", "opus"}

    def test_variant_models_none_uses_defaults(self, tmp_path: Path) -> None:
        """Variant with models=None falls back to defaults.models."""
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet", "haiku"],
                profiles=["empty"],
                reps=1,
            ),
            variants=[VariantConfig(label="v1")],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        runs = expand_experiment(
            config, task_dirs, profile_paths, tmp_path / "results"
        )

        assert len(runs) == 2
        assert {r.model for r in runs} == {"sonnet", "haiku"}

    def test_missing_profile_raises(self, tmp_path: Path) -> None:
        config = ExperimentConfig(
            name="test",
            defaults=ExperimentDefaults(
                tasks=["t1"],
                models=["sonnet"],
                profiles=["nonexistent_profile"],
                reps=1,
            ),
            variants=[VariantConfig(label="v1")],
        )
        task_dirs = {"t1": tmp_path / "tasks" / "t1"}
        profile_paths = {"empty": tmp_path / "profiles" / "empty" / "CLAUDE.md"}

        with pytest.raises(ValueError, match="not found"):
            expand_experiment(config, task_dirs, profile_paths, tmp_path / "results")
