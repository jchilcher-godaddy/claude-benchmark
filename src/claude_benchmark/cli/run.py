"""CLI run command: execute benchmark tasks against CLAUDE.md profiles."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from claude_benchmark.tasks.registry import TaskRegistry

console = Console()
logger = logging.getLogger(__name__)

VALID_MODELS = {"haiku", "sonnet", "opus"}


def run(
    profile: str = typer.Option(
        ..., help="CLAUDE.md profile path(s), comma-separated"
    ),
    model: str = typer.Option(
        "sonnet",
        help="Model(s) to use: haiku, sonnet, opus. Comma-separated for matrix",
    ),
    tasks: Optional[str] = typer.Option(
        None, help="Task name(s) to run, comma-separated. Omit for all tasks"
    ),
    runs: int = typer.Option(
        5, min=3, help="Number of runs per task/profile/model combination (min 3)"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress progress, print only results path"
    ),
    keep_workspaces: bool = typer.Option(
        False,
        "--keep-workspaces",
        help="Preserve temp workspace directories for debugging",
    ),
):
    """Run benchmark tasks against CLAUDE.md profiles."""
    # Parse comma-separated profiles
    profiles = [Path(p.strip()) for p in profile.split(",")]
    for p in profiles:
        if not p.exists():
            console.print(
                f"[red]Error:[/red] Profile not found: {p}", highlight=False
            )
            raise typer.Exit(1)

    # Parse and validate models
    models = [m.strip() for m in model.split(",")]
    for m in models:
        if m not in VALID_MODELS:
            console.print(
                f"[red]Error:[/red] Invalid model '{m}'. "
                f"Choose from: {', '.join(sorted(VALID_MODELS))}",
                highlight=False,
            )
            raise typer.Exit(1)

    # Load tasks via registry
    builtin_dir = Path("tasks/builtin")
    custom_dir = Path("tasks/custom")
    search_dirs: list[Path] = []
    if builtin_dir.exists():
        search_dirs.append(builtin_dir)
    if custom_dir.exists():
        search_dirs.append(custom_dir)

    if not search_dirs:
        console.print(
            "[red]Error:[/red] No task directories found", highlight=False
        )
        raise typer.Exit(1)

    registry = TaskRegistry.from_directories(*search_dirs)

    # Filter tasks if specified
    if tasks:
        task_names = [t.strip() for t in tasks.split(",")]
        selected_tasks = []
        for name in task_names:
            task = registry.by_name(name)
            if task is None:
                console.print(
                    f"[red]Error:[/red] Task not found: '{name}'",
                    highlight=False,
                )
                raise typer.Exit(1)
            selected_tasks.append(task)
    else:
        selected_tasks = registry.all

    if not selected_tasks:
        console.print(
            "[red]Error:[/red] No tasks found to run", highlight=False
        )
        raise typer.Exit(1)

    # Build task_dirs mapping (task name -> directory path)
    task_dirs: dict[str, Path] = {}
    for search_dir in search_dirs:
        for child in sorted(search_dir.iterdir()):
            if child.is_dir() and (child / "task.toml").exists():
                from claude_benchmark.tasks.loader import load_task

                try:
                    loaded = load_task(child)
                    task_dirs[loaded.name] = child
                except Exception:
                    pass

    # Verify all selected tasks have known directories
    for t in selected_tasks:
        if t.name not in task_dirs:
            console.print(
                f"[red]Error:[/red] Cannot find task directory for: '{t.name}'",
                highlight=False,
            )
            raise typer.Exit(1)

    if not quiet:
        console.print(
            f"Running benchmark: {len(selected_tasks)} tasks x "
            f"{len(profiles)} profiles x {len(models)} models x {runs} runs = "
            f"{len(selected_tasks) * len(profiles) * len(models) * runs} total runs"
        )

    # Run the benchmark matrix
    from claude_benchmark.engine.orchestrator import run_benchmark_matrix

    results_path = asyncio.run(
        run_benchmark_matrix(
            tasks=selected_tasks,
            task_dirs=task_dirs,
            profiles=profiles,
            models=models,
            runs_per=runs,
            quiet=quiet,
            keep_workspaces=keep_workspaces,
        )
    )

    if quiet:
        typer.echo(str(results_path))
    else:
        console.print(f"\n[bold]Results:[/bold] {results_path}")
