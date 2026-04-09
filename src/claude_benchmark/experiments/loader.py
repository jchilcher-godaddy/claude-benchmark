"""Load and expand experiment configurations from TOML files."""

import tomllib
from pathlib import Path

from claude_benchmark.execution.context_padding import generate_padding
from claude_benchmark.execution.parallel import BenchmarkRun
from claude_benchmark.experiments.schema import ExperimentConfig


def load_experiment(config_path: Path) -> ExperimentConfig:
    """Load and validate an experiment config from a TOML file.

    Args:
        config_path: Path to the TOML experiment configuration file.

    Returns:
        Validated ExperimentConfig instance.

    Raises:
        FileNotFoundError: If config_path does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
        pydantic.ValidationError: If the config structure is invalid.
    """
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)
    return ExperimentConfig.model_validate(raw)


def expand_experiment(
    config: ExperimentConfig,
    task_dirs: dict[str, Path],
    profile_paths: dict[str, Path],
    results_dir: Path,
) -> list[BenchmarkRun]:
    """Expand an ExperimentConfig into a flat list of BenchmarkRun instances.

    Args:
        config: The validated experiment configuration.
        task_dirs: Mapping from task name to task directory path.
        profile_paths: Mapping from profile name to profile file path.
        results_dir: Base directory for storing results.

    Returns:
        Flat list of BenchmarkRun instances covering all variants x tasks x profiles x models x reps.

    Raises:
        ValueError: If any referenced task or profile is not found in the provided mappings.
    """
    runs = []
    for variant in config.variants:
        for task_name in config.defaults.tasks:
            if task_name not in task_dirs:
                raise ValueError(f"Task '{task_name}' not found")
            for profile_name in config.defaults.profiles:
                if profile_name not in profile_paths:
                    raise ValueError(f"Profile '{profile_name}' not found")
                variant_models = variant.models or config.defaults.models
                for model in variant_models:
                    for rep in range(1, config.defaults.reps + 1):
                        temp = (
                            variant.temperature
                            if variant.temperature is not None
                            else config.defaults.temperature
                        )
                        prefix = variant.prompt_prefix or ""
                        if variant.padding_tokens is not None:
                            prefix = generate_padding(variant.padding_tokens) + prefix
                        runs.append(
                            BenchmarkRun(
                                task_name=task_name,
                                profile_name=profile_name,
                                model=model,
                                run_number=rep,
                                task_dir=task_dirs[task_name],
                                profile_path=profile_paths[profile_name],
                                results_dir=results_dir,
                                system_prompt_extra=variant.system_prompt_extra,
                                prompt_prefix=prefix or None,
                                variant_label=variant.label,
                                temperature=temp,
                            )
                        )
    return runs
