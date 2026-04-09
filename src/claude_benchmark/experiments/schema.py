"""Pydantic models for experiment configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VariantConfig(BaseModel):
    """One treatment arm in an experiment."""

    label: str
    prompt_prefix: str | None = None
    system_prompt_extra: str | None = None
    temperature: float | None = None
    padding_tokens: int | None = None
    models: list[str] | None = None


class ExperimentDefaults(BaseModel):
    """Default settings applied to all variants."""

    tasks: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=lambda: ["sonnet"])
    profiles: list[str] = Field(default_factory=lambda: ["empty"])
    reps: int = 10
    temperature: float | None = None


class ExperimentConfig(BaseModel):
    """Top-level experiment configuration."""

    name: str
    description: str = ""
    defaults: ExperimentDefaults = Field(default_factory=ExperimentDefaults)
    variants: list[VariantConfig]
