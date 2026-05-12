"""Pydantic models for experiment configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VariantConfig(BaseModel):
    """One treatment arm in an experiment."""

    model_config = ConfigDict(extra="forbid")

    label: str
    prompt_prefix: str | None = None
    system_prompt_extra: str | None = None
    temperature: float | None = None
    padding_tokens: int | None = None
    models: list[str] | None = None
    # Multi-turn conversation support
    follow_up_prompts: list[str] | None = None
    # Declared for forward compat: recognized by the schema so experiment TOMLs
    # can opt in, but the worker-side execution of tests between turns is not
    # yet wired up. Leaving it here keeps strict validation on while pending.
    run_tests_between_turns: bool = False
    # CLI-agent execution fields (agent-mechanism experiment)
    use_cli: bool = False
    agent_definition: dict | None = None


class ExperimentDefaults(BaseModel):
    """Default settings applied to all variants."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=lambda: ["sonnet"])
    profiles: list[str] = Field(default_factory=lambda: ["empty"])
    reps: int = 10
    temperature: float | None = None


class ExperimentConfig(BaseModel):
    """Top-level experiment configuration."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    defaults: ExperimentDefaults = Field(default_factory=ExperimentDefaults)
    variants: list[VariantConfig]
