"""CLI rescore command: score existing unscored run results."""

from __future__ import annotations

import asyncio
import json
import tomllib
from pathlib import Path

import typer
from rich.console import Console

from claude_benchmark.cli.discovery import discover_all_profiles, discover_all_tasks
from claude_benchmark.execution.parallel import BenchmarkRun, RunResult
from claude_benchmark.execution.worker import execute_single_run, write_result_atomic
from claude_benchmark.scoring.pipeline import score_all_runs

console = Console()


def _load_variant_configs(results_dir: Path) -> dict[str, dict]:
    """Load variant configs from the experiment manifest or TOML.

    Returns a mapping of variant_label -> {system_prompt_extra, prompt_prefix, temperature}.
    """
    # Try to find the experiment name from manifest.json
    manifest_path = results_dir / "manifest.json"
    if not manifest_path.exists():
        return {}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    experiment_name = manifest.get("experiment_name")
    if not experiment_name:
        return {}

    # Look for the experiment TOML in the experiments/ directory
    experiments_dir = results_dir.parent.parent / "experiments"
    if not experiments_dir.exists():
        # Try relative to repo root
        for parent in results_dir.parents:
            candidate = parent / "experiments"
            if candidate.exists():
                experiments_dir = candidate
                break

    toml_path = experiments_dir / f"{experiment_name}.toml"
    if not toml_path.exists():
        return {}

    try:
        with open(toml_path, "rb") as f:
            toml_data = tomllib.load(f)
    except Exception:
        return {}

    configs: dict[str, dict] = {}
    for variant in toml_data.get("variants", []):
        if not isinstance(variant, dict):
            continue
        label = variant.get("label")
        if label:
            configs[label] = {
                "system_prompt_extra": variant.get("system_prompt_extra"),
                "prompt_prefix": variant.get("prompt_prefix"),
                "temperature": variant.get("temperature"),
            }
    return configs


def _resolve_output_dir(output_dir_str: str | None, results_dir: Path) -> Path | None:
    """Resolve an output_dir string from a run JSON, handling relative paths."""
    if not output_dir_str:
        return None
    output_dir = Path(output_dir_str)
    if output_dir.exists():
        return output_dir
    if output_dir.is_absolute():
        return None
    # Try resolving relative to results_dir ancestors (repo root)
    for parent in [results_dir.parent, *results_dir.parents]:
        candidate = parent / output_dir
        if candidate.exists():
            return candidate
    return None


def _load_results(
    results_dir: Path,
    task_dirs: dict[str, Path],
    profile_paths: dict[str, Path],
    force: bool = False,
    rerun_empty: bool = False,
    variant_configs: dict[str, dict] | None = None,
    use_gocode: bool = False,
) -> list[RunResult]:
    """Walk results_dir for run-*.json files and reconstruct RunResult objects.

    Args:
        results_dir: Root results directory to scan.
        task_dirs: Mapping of task name to task directory path.
        profile_paths: Mapping of profile slug to profile path.
        force: If True, include already-scored runs too.
        rerun_empty: If True, also include degraded runs with empty output dirs.
        variant_configs: Optional variant label -> config mapping for re-execution.

    Returns:
        List of reconstructed RunResult objects ready for scoring.
    """
    run_results: list[RunResult] = []

    for run_file in sorted(results_dir.rglob("run-*.json")):
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("status") != "success":
            continue

        scores = data.get("scores")
        has_scores = scores is not None

        # Decide whether to include this run
        if has_scores and not force:
            # With --rerun-empty, include degraded runs that have empty output dirs
            if rerun_empty and isinstance(scores, dict) and scores.get("degraded"):
                pass  # fall through to include
            else:
                continue

        task_name = data.get("task_name")
        profile_name = data.get("profile_name")
        model = data.get("model")
        run_number = data.get("run_number")

        if not all([task_name, profile_name, model, run_number is not None]):
            console.print(
                f"[yellow]Warning:[/yellow] Skipping {run_file}: missing required fields",
                highlight=False,
            )
            continue

        task_dir = task_dirs.get(task_name)
        if task_dir is None:
            console.print(
                f"[yellow]Warning:[/yellow] Skipping {run_file}: unknown task '{task_name}'",
                highlight=False,
            )
            continue

        profile_path = profile_paths.get(profile_name)
        if profile_path is None:
            console.print(
                f"[yellow]Warning:[/yellow] Skipping {run_file}: unknown profile '{profile_name}'",
                highlight=False,
            )
            continue

        output_dir = _resolve_output_dir(data.get("output_dir"), results_dir)
        if output_dir is None:
            console.print(
                f"[yellow]Warning:[/yellow] Skipping {run_file}: output_dir missing or not found",
                highlight=False,
            )
            continue

        variant_label = data.get("variant_label")
        vc = (variant_configs or {}).get(variant_label or "", {})

        run = BenchmarkRun(
            task_name=task_name,
            profile_name=profile_name,
            model=model,
            run_number=run_number,
            task_dir=task_dir,
            profile_path=profile_path,
            results_dir=results_dir,
            variant_label=variant_label,
            temperature=data.get("temperature") or vc.get("temperature"),
            system_prompt_extra=vc.get("system_prompt_extra"),
            prompt_prefix=vc.get("prompt_prefix"),
            use_gocode=use_gocode,
        )

        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cost=data.get("cost", 0.0),
            duration_seconds=data.get("duration_seconds", 0.0),
        )

        run_results.append(result)

    return run_results


def _rescore_single(
    results_dir: Path,
    task_dirs: dict[str, Path],
    profile_paths: dict[str, Path],
    skip_llm_judge: bool,
    strict_scoring: bool,
    force: bool,
    rerun_empty: bool,
    use_gocode: bool = False,
) -> None:
    """Rescore a single results directory."""
    if not results_dir.exists():
        console.print(
            f"[red]Error:[/red] Results directory not found: {results_dir}",
            highlight=False,
        )
        raise typer.Exit(1)

    # Load variant configs from experiment TOML (needed for re-execution)
    variant_configs = _load_variant_configs(results_dir) if rerun_empty else None

    # Find results to process
    label = "all" if force else ("unscored + degraded-empty" if rerun_empty else "unscored")
    console.print(f"Scanning {results_dir} for {label} runs...")
    run_results = _load_results(
        results_dir, task_dirs, profile_paths,
        force=force, rerun_empty=rerun_empty, variant_configs=variant_configs,
        use_gocode=use_gocode,
    )

    if not run_results:
        console.print("No runs to rescore.")
        return

    console.print(f"Found {len(run_results)} runs to rescore.")

    # Re-execute runs with empty output directories
    if rerun_empty:
        empty_runs = [
            r for r in run_results
            if r.output_dir and r.output_dir.exists() and not any(r.output_dir.iterdir())
        ]
        if empty_runs:
            console.print(f"Re-executing {len(empty_runs)} runs with empty output directories...")
            for result in empty_runs:
                console.print(f"  Re-executing {result.run.result_key}...")
                new_result = asyncio.run(execute_single_run(result.run))
                # Update the result in place with new execution data
                result.status = new_result.status
                result.output_dir = new_result.output_dir
                result.input_tokens = new_result.input_tokens
                result.output_tokens = new_result.output_tokens
                result.total_tokens = new_result.total_tokens
                result.cost = new_result.cost
                result.duration_seconds = new_result.duration_seconds
                result.error = new_result.error
                if new_result.status == "success":
                    write_result_atomic(new_result)
                    console.print(f"    [green]Success[/green]")
                else:
                    console.print(
                        f"    [red]Failed:[/red] {new_result.error}",
                        highlight=False,
                    )
            # Filter out failed re-executions
            run_results = [r for r in run_results if r.status == "success"]
        else:
            console.print("No runs with empty output directories found.")

    # Score all runs
    scored_results, aggregation = score_all_runs(
        run_results,
        skip_llm=skip_llm_judge,
        strict=strict_scoring,
    )

    # Write scores back to disk
    written = 0
    for result in scored_results:
        if result.scores:
            write_result_atomic(result)
            written += 1

    scored_count = sum(1 for r in scored_results if r.scores and not r.scores.get("degraded"))
    degraded_count = sum(1 for r in scored_results if r.scores and r.scores.get("degraded"))

    console.print(
        f"Rescored: {written} | Clean: {scored_count} | Degraded: {degraded_count} | "
        f"LLM judge: {'skipped' if skip_llm_judge else 'enabled'}"
    )

    if aggregation:
        console.print("\n[bold]Score Aggregation by Variant:[/bold]")
        for variant_key, agg_data in sorted(aggregation.items()):
            scores_agg = agg_data.get("scores", {})
            composite_agg = scores_agg.get("composite")
            if composite_agg:
                mean = composite_agg.get("mean", 0)
                ci_lower = composite_agg.get("ci_lower", 0)
                ci_upper = composite_agg.get("ci_upper", 0)
                console.print(
                    f"  {variant_key}: {mean:.1f} (95% CI: {ci_lower:.1f}-{ci_upper:.1f})"
                )

    console.print(f"\n[bold]Results:[/bold] {results_dir}")


def rescore(
    results_dirs: list[Path] = typer.Argument(
        ...,
        help="Path(s) to results directories to rescore",
    ),
    skip_llm_judge: bool = typer.Option(
        False,
        "--skip-llm-judge",
        help="Skip LLM-as-judge scoring",
    ),
    strict_scoring: bool = typer.Option(
        False,
        "--strict-scoring",
        help="Fail if any scorer errors",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Rescore ALL runs, not just unscored ones",
    ),
    rerun_empty: bool = typer.Option(
        False,
        "--rerun-empty",
        help="Re-execute runs with empty output directories before scoring",
    ),
    gocode: bool = typer.Option(
        False,
        "--gocode",
        help="Use GoCode API endpoint instead of AWS Bedrock for LLM judge scoring. "
        "Requires ANTHROPIC_BASE_URL and GOCODE_API_TOKEN env vars.",
    ),
) -> None:
    """Rescore existing benchmark results that are missing scores.

    Walks the results directory for successful runs with null/missing scores,
    reconstructs RunResult objects, and passes them through the scoring pipeline.

    Accepts one or more results directories.
    """
    if gocode:
        from claude_benchmark.execution.client import validate_gocode_env

        missing = validate_gocode_env()
        if missing:
            console.print(f"[red]Error:[/red] --gocode requires: {', '.join(missing)}")
            raise typer.Exit(1)
    else:
        from claude_benchmark.execution.client import (
            attempt_sso_login,
            validate_bedrock_credentials,
        )

        cred_error = validate_bedrock_credentials()
        if cred_error:
            console.print(f"\n[yellow]AWS credential issue:[/yellow] {cred_error}")
            if attempt_sso_login(console):
                console.print()
            else:
                console.print("[red]Cannot proceed without valid AWS credentials.[/red]")
                raise typer.Exit(1)

    # Discover tasks and profiles once for all directories
    task_dirs = discover_all_tasks()
    profile_paths = discover_all_profiles()

    for results_dir in results_dirs:
        if len(results_dirs) > 1:
            console.print(f"\n[bold]{'─' * 60}[/bold]")
            console.print(f"[bold]Processing:[/bold] {results_dir}")
        _rescore_single(
            results_dir, task_dirs, profile_paths,
            skip_llm_judge=skip_llm_judge,
            strict_scoring=strict_scoring,
            force=force,
            rerun_empty=rerun_empty,
            use_gocode=gocode,
        )
