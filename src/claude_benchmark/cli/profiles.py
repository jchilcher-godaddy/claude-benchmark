"""CLI command for listing benchmark profiles."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from claude_benchmark.profiles.loader import discover_profiles
from claude_benchmark.profiles.token_counter import count_tokens

console = Console()

PROFILES_DIR = Path("profiles")


def list_profiles(
    profiles_dir: Path = typer.Option(
        PROFILES_DIR,
        help="Directory containing profile .md files",
    ),
) -> None:
    """List all available benchmark profiles."""
    profiles = discover_profiles(profiles_dir)

    if not profiles:
        console.print("[yellow]No profiles found.[/yellow]")
        console.print(f"Add .md files to {profiles_dir}/")
        raise typer.Exit(1)

    table = Table(title="Available Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Variant")
    table.add_column("Tokens", justify="right", style="green")
    table.add_column("Exact", justify="center")

    for profile in profiles:
        token_count, is_exact = count_tokens(profile.content, use_api=False)
        table.add_row(
            profile.slug,
            profile.metadata.description,
            profile.metadata.variant or "-",
            f"{token_count:,}",
            "Y" if is_exact else "~",
        )

    console.print(table)
