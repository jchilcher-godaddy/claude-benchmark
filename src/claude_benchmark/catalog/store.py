"""Catalog CRUD operations for managing benchmark result sets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from claude_benchmark.catalog.models import Catalog, CatalogEntry
from claude_benchmark.reporting.loader import load_manifest


def default_catalog_path() -> Path:
    """Return the default catalog file path."""
    return Path("results/catalog.json")


def load_catalog(path: Path | None = None) -> Catalog:
    """Load the catalog from disk, or return empty catalog if missing.

    Args:
        path: Path to catalog file. Uses default_catalog_path() if None.

    Returns:
        Loaded Catalog or empty Catalog if file doesn't exist.
    """
    if path is None:
        path = default_catalog_path()

    if not path.exists():
        return Catalog()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Catalog(**data)
    except (json.JSONDecodeError, OSError):
        return Catalog()


def save_catalog(catalog: Catalog, path: Path | None = None) -> None:
    """Save catalog to disk with atomic write.

    Args:
        catalog: Catalog to save.
        path: Path to save to. Uses default_catalog_path() if None.
    """
    if path is None:
        path = default_catalog_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write via temp file + rename
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(catalog.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp_path.rename(path)


def next_run_id(catalog: Catalog) -> str:
    """Generate the next sequential run ID.

    Args:
        catalog: Catalog to scan for existing IDs.

    Returns:
        Next run ID in format "run-NNN" (zero-padded to 3 digits).
    """
    if not catalog.entries:
        return "run-001"

    # Extract numeric part from existing run-NNN IDs
    max_num = 0
    for entry in catalog.entries:
        if entry.run_id.startswith("run-"):
            try:
                num = int(entry.run_id[4:])
                max_num = max(max_num, num)
            except ValueError:
                continue

    return f"run-{max_num + 1:03d}"


def validate_results_dir(path: Path) -> tuple[bool, str]:
    """Validate that a results directory is intact and loadable.

    Args:
        path: Path to results directory.

    Returns:
        (is_valid, error_message). error_message is empty string if valid.
    """
    path = Path(path)

    if not path.exists():
        return False, f"Directory does not exist: {path}"

    if not path.is_dir():
        return False, f"Path is not a directory: {path}"

    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return False, f"Missing manifest.json in {path}"

    # Check for at least one run file (either storage or parallel format)
    storage_files = list(path.rglob("run_*.json"))
    parallel_files = list(path.rglob("run-*.json"))

    if not storage_files and not parallel_files:
        return False, f"No run result files found in {path}"

    return True, ""


def intake_run(
    catalog: Catalog,
    results_dir: Path,
    name: str | None = None,
    tags: list[str] | None = None,
    run_id: str | None = None,
    force: bool = False,
) -> CatalogEntry:
    """Add a results directory to the catalog.

    Args:
        catalog: Catalog to add entry to.
        results_dir: Path to results directory.
        name: Human-readable name. Defaults to directory name.
        tags: Tags for filtering. Defaults to empty list.
        run_id: Explicit run ID. Auto-generated if None.
        force: If True, remove existing entry with same path first.

    Returns:
        The created CatalogEntry.

    Raises:
        ValueError: If results_dir is invalid or already in catalog (unless force=True).
    """
    results_dir = Path(results_dir).resolve()

    # Validate directory
    is_valid, error = validate_results_dir(results_dir)
    if not is_valid:
        raise ValueError(error)

    # Check for duplicate path
    existing = None
    for entry in catalog.entries:
        if Path(entry.results_path).resolve() == results_dir:
            existing = entry
            break

    if existing and not force:
        raise ValueError(
            f"Results directory already in catalog as {existing.run_id}. "
            "Use force=True to replace."
        )

    if existing and force:
        catalog.entries.remove(existing)

    # Load manifest
    manifest = load_manifest(results_dir)

    # Generate or use provided run_id
    if run_id is None:
        run_id = next_run_id(catalog)

    # Use directory name as default name
    if name is None:
        name = results_dir.name

    # Count run files
    storage_files = list(results_dir.rglob("run_*.json"))
    parallel_files = list(results_dir.rglob("run-*.json"))
    total_runs = len(storage_files) + len(parallel_files)

    # Create entry
    entry = CatalogEntry(
        run_id=run_id,
        name=name,
        timestamp=manifest.get("timestamp", ""),
        results_path=str(results_dir),
        tags=tags or [],
        models=manifest.get("models", []),
        profiles=manifest.get("profiles", []),
        tasks=manifest.get("tasks", []),
        variants=manifest.get("variants", []),
        total_runs=total_runs,
        experiment_name=manifest.get("experiment_name"),
        intake_timestamp=datetime.now(timezone.utc).isoformat(),
    )

    catalog.entries.append(entry)
    return entry


def find_entries(
    catalog: Catalog,
    run_ids: list[str] | None = None,
    tags: list[str] | None = None,
    names: list[str] | None = None,
) -> list[CatalogEntry]:
    """Find catalog entries by run ID, tag, or name.

    Returns the union of all matches.

    Args:
        catalog: Catalog to search.
        run_ids: Exact run IDs to match.
        tags: Tags to match (any tag matches).
        names: Name substrings to match.

    Returns:
        List of matching CatalogEntry objects (no duplicates).
    """
    seen_ids: set[str] = set()
    matches: list[CatalogEntry] = []

    def _add(entry: CatalogEntry) -> None:
        if entry.run_id not in seen_ids:
            seen_ids.add(entry.run_id)
            matches.append(entry)

    if run_ids:
        for entry in catalog.entries:
            if entry.run_id in run_ids:
                _add(entry)

    if tags:
        for entry in catalog.entries:
            if any(tag in entry.tags for tag in tags):
                _add(entry)

    if names:
        for entry in catalog.entries:
            if any(name.lower() in entry.name.lower() for name in names):
                _add(entry)

    return matches


def remove_entry(catalog: Catalog, run_id: str) -> CatalogEntry:
    """Remove an entry from the catalog by run ID.

    Args:
        catalog: Catalog to modify.
        run_id: Run ID to remove.

    Returns:
        The removed entry.

    Raises:
        KeyError: If run_id not found in catalog.
    """
    for entry in catalog.entries:
        if entry.run_id == run_id:
            catalog.entries.remove(entry)
            return entry

    raise KeyError(f"Run ID not found: {run_id}")


def tag_entry(catalog: Catalog, run_id: str, tags: list[str]) -> CatalogEntry:
    """Add tags to a catalog entry.

    Args:
        catalog: Catalog containing the entry.
        run_id: Run ID to tag.
        tags: Tags to add (duplicates ignored).

    Returns:
        Updated entry.

    Raises:
        KeyError: If run_id not found in catalog.
    """
    for i, entry in enumerate(catalog.entries):
        if entry.run_id == run_id:
            # Create new entry with updated tags (entries are immutable)
            updated_tags = list(set(entry.tags + tags))
            updated_entry = entry.model_copy(update={"tags": updated_tags})
            catalog.entries[i] = updated_entry
            return updated_entry

    raise KeyError(f"Run ID not found: {run_id}")
