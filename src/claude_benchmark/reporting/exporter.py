"""Raw data export for benchmark results (JSON and CSV).

Exports BenchmarkResults to disk as JSON and CSV files.
JSON uses pretty-printing with NaN/Infinity sanitization.
CSV flattens to one row per run with score dimensions as columns.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from claude_benchmark.reporting.models import BenchmarkResults


def export_json(results: BenchmarkResults, output_dir: Path) -> Path:
    """Write benchmark results as pretty-printed JSON.

    Args:
        results: The benchmark results to export.
        output_dir: Directory to write the JSON file to.

    Returns:
        Path to the written JSON file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark-results.json"

    export_data = results.to_export_dict()
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, default=str)

    return json_path


def export_csv(results: BenchmarkResults, output_dir: Path) -> Path:
    """Write benchmark results as CSV (one row per run).

    Uses Python's csv.DictWriter for lightweight export without
    requiring pandas as a dependency.

    Args:
        results: The benchmark results to export.
        output_dir: Directory to write the CSV file to.

    Returns:
        Path to the written CSV file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "benchmark-results.csv"

    rows = results.to_csv_rows()
    if not rows:
        # Write empty file with no headers if no data
        csv_path.write_text("")
        return csv_path

    # Collect all possible fieldnames across all rows (score dimensions may vary)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def export_raw_data(results: BenchmarkResults, output_dir: Path) -> tuple[Path, Path]:
    """Export benchmark results as both JSON and CSV.

    Creates output_dir if needed. Prints paths to stdout.

    Args:
        results: The benchmark results to export.
        output_dir: Directory to write both files to.

    Returns:
        Tuple of (json_path, csv_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = export_json(results, output_dir)
    csv_path = export_csv(results, output_dir)

    print(f"Exported: {json_path}")
    print(f"Exported: {csv_path}")

    return json_path, csv_path
