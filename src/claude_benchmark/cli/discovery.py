"""Shared task and profile discovery utilities.

Extracted from experiment.py so both experiment and rescore commands
can reuse them without circular imports.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from claude_benchmark.profiles.loader import discover_profiles

console = Console()


def discover_all_tasks() -> dict[str, Path]:
    """Discover all tasks from builtin and custom directories.

    Returns:
        Mapping from task name to task directory path.
    """
    builtin_dir = Path("tasks/builtin")
    custom_dir = Path("tasks/custom")
    search_dirs: list[Path] = []
    if builtin_dir.exists():
        search_dirs.append(builtin_dir)
    if custom_dir.exists():
        search_dirs.append(custom_dir)

    if not search_dirs:
        console.print(
            "[red]Error:[/red] No task directories found (tasks/builtin or tasks/custom)",
            highlight=False,
        )
        raise typer.Exit(1)

    task_dirs: dict[str, Path] = {}
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for child in sorted(search_dir.iterdir()):
            if child.is_dir() and (child / "task.toml").exists():
                from claude_benchmark.tasks.loader import load_task

                try:
                    loaded = load_task(child)
                    task_dirs[loaded.name] = child
                except Exception:
                    pass

    return task_dirs


def discover_all_profiles() -> dict[str, Path]:
    """Discover all profiles from the default profiles directory.

    Returns:
        Mapping from profile slug to profile path.
    """
    profiles = discover_profiles()
    if not profiles:
        console.print(
            "[red]Error:[/red] No profiles found in profiles/ directory",
            highlight=False,
        )
        raise typer.Exit(1)

    return {p.slug: p.path for p in profiles}
