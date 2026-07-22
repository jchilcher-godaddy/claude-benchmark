"""Deterministic SHA-256 hashing for tasks and judge-prompt provenance.

Hashes are content-addressed and ordering-stable, so that the same inputs
on disk always produce the same digest regardless of filesystem traversal
order. This lets a published paper cite a single ``task_set_hash`` and a
later reader verify their checkout matches.

Design notes:
    - Files are read with ``Path.read_bytes()``; we hash raw bytes, not
      decoded text. Line-ending normalization is intentionally NOT applied:
      a CRLF/LF change is a real change to the corpus.
    - Files within a task are walked in sorted POSIX-path order before
      being concatenated for hashing, so the per-task digest is stable
      across operating systems.
    - ``__pycache__`` directories and ``*.pyc`` files are skipped because
      they are derived artifacts that change with every Python version.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Files / directories we never include in the task-set hash because they
# are local build artifacts, not source-of-truth task content.
_HASH_EXCLUDE_DIRS: frozenset[str] = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache"})
_HASH_EXCLUDE_SUFFIXES: frozenset[str] = frozenset({".pyc", ".pyo"})


def hash_string(s: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8-encoded string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _hash_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def _iter_task_files(task_dir: Path) -> list[Path]:
    """Walk a task directory, returning files in deterministic sorted order.

    Excludes derived artifacts (``__pycache__``, ``.pyc``, etc.) so that
    a freshly-cloned and a previously-imported tree produce the same hash.
    """
    files: list[Path] = []
    for entry in task_dir.rglob("*"):
        if not entry.is_file():
            continue
        if any(part in _HASH_EXCLUDE_DIRS for part in entry.parts):
            continue
        if entry.suffix in _HASH_EXCLUDE_SUFFIXES:
            continue
        files.append(entry)
    # Sort by POSIX-style relative path for cross-OS determinism.
    files.sort(key=lambda p: p.relative_to(task_dir).as_posix())
    return files


def _hash_task_dir(task_dir: Path) -> str:
    """Hash all source files inside a single task directory.

    The digest is over ``relpath || NUL || content || NUL`` for each file,
    in sorted-relpath order. Including the relative path in the hash
    ensures a rename (without content changes) still flips the digest.
    """
    hasher = hashlib.sha256()
    for file_path in _iter_task_files(task_dir):
        rel = file_path.relative_to(task_dir).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(file_path.read_bytes())
        hasher.update(b"\x00")
    return hasher.hexdigest()


def hash_task_set(tasks_root: Path) -> dict:
    """Compute a deterministic content hash of an entire task corpus.

    Args:
        tasks_root: Either the top-level ``tasks/`` directory (containing
            ``builtin/`` and ``custom/`` subdirs) or a single subdirectory
            containing task folders directly.

    Returns:
        A dict with three keys:
            - ``task_set_hash``: SHA-256 over the sorted list of
              ``"<task_id>:<task_hash>"`` lines. Stable across OSes.
            - ``task_count``: Number of task directories included.
            - ``task_hashes``: Mapping of ``task_id -> sha256`` for each
              task. ``task_id`` is the POSIX relative path from
              ``tasks_root`` (e.g. ``"builtin/bug-fix-01"``).

    Raises:
        FileNotFoundError: If ``tasks_root`` does not exist.
    """
    tasks_root = Path(tasks_root)
    if not tasks_root.exists():
        raise FileNotFoundError(f"Task root does not exist: {tasks_root}")

    task_dirs: list[Path] = []
    # A "task directory" is any directory containing a task.toml. Walking
    # for task.toml is more robust than assuming a fixed depth (handles
    # both tasks/builtin/<id>/ and direct tasks_root/<id>/ layouts, plus
    # any future nesting).
    for toml in tasks_root.rglob("task.toml"):
        if toml.is_file():
            task_dirs.append(toml.parent)
    task_dirs.sort(key=lambda p: p.relative_to(tasks_root).as_posix())

    task_hashes: dict[str, str] = {}
    for task_dir in task_dirs:
        task_id = task_dir.relative_to(tasks_root).as_posix()
        task_hashes[task_id] = _hash_task_dir(task_dir)

    # Aggregate: sort by task_id (already done) and hash the join.
    aggregate = hashlib.sha256()
    for task_id in sorted(task_hashes):
        aggregate.update(f"{task_id}:{task_hashes[task_id]}\n".encode("utf-8"))

    return {
        "task_set_hash": aggregate.hexdigest(),
        "task_count": len(task_hashes),
        "task_hashes": task_hashes,
    }


def hash_judge_prompt() -> dict:
    """Hash the LLM judge prompt artifacts from ``scoring.prompts``.

    Returns hashes for the four pieces that, taken together, define the
    scoring contract: system prompt, criteria list, output schema, and the
    full module source (catches changes to helper functions like
    ``format_judge_user_prompt`` that aren't visible in the constants).

    Returns:
        Dict with keys ``system_prompt_sha256``, ``criteria_sha256``,
        ``schema_sha256``, ``judge_module_sha256``.
    """
    import importlib
    import importlib.util
    import inspect
    import json
    import sys

    # Import the prompts module directly without going through
    # ``claude_benchmark.scoring.__init__`` (which has heavy transitive
    # imports — scipy, psutil, etc. — that aren't needed for hashing).
    # Try the cheap path first; fall back to a file-path-based loader
    # so this works even in stripped-down environments.
    if "claude_benchmark.scoring.prompts" in sys.modules:
        judge_prompts = sys.modules["claude_benchmark.scoring.prompts"]
    else:
        try:
            judge_prompts = importlib.import_module("claude_benchmark.scoring.prompts")
        except ImportError:
            here = Path(__file__).resolve().parent
            prompts_path = here.parent / "scoring" / "prompts.py"
            spec = importlib.util.spec_from_file_location(
                "_cb_judge_prompts", prompts_path
            )
            if spec is None or spec.loader is None:
                raise
            judge_prompts = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(judge_prompts)

    criteria_canonical = json.dumps(
        judge_prompts.BUILTIN_CRITERIA,
        sort_keys=True,
        separators=(",", ":"),
    )
    schema_canonical = json.dumps(
        judge_prompts.JUDGE_OUTPUT_SCHEMA,
        sort_keys=True,
        separators=(",", ":"),
    )

    try:
        module_source = inspect.getsource(judge_prompts)
    except (OSError, TypeError):
        # Frozen or namespace-loaded modules may not expose source.
        module_source = ""

    return {
        "system_prompt_sha256": hash_string(judge_prompts.JUDGE_SYSTEM_PROMPT),
        "criteria_sha256": hash_string(criteria_canonical),
        "schema_sha256": hash_string(schema_canonical),
        "judge_module_sha256": hash_string(module_source),
        "judge_model_alias": judge_prompts.DEFAULT_JUDGE_MODEL,
    }
