"""Capture the execution environment for an experiment run.

What we record:
    - Python version + platform string (so a reader knows which interpreter
      produced the corpus).
    - ``cb_version``: claude-benchmark's own version (read from package
      metadata or pyproject.toml).
    - ``pip_freeze``: a sorted ``["pkg==ver", ...]`` list of every
      installed distribution.
    - ``git_commit`` and ``git_dirty``: provenance for the source tree
      that produced the run.

All git/subprocess operations degrade gracefully — a missing ``git``
binary, a non-repo working directory, or a frozen interpreter must not
crash the experiment.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _read_cb_version() -> str:
    """Resolve the installed claude-benchmark version.

    Tries ``importlib.metadata`` first (works for both editable and
    wheel installs); falls back to parsing ``pyproject.toml`` so a
    fresh checkout without ``pip install`` still records something.
    Returns ``"unknown"`` if nothing can be resolved.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("claude-benchmark")
    except (PackageNotFoundError, ImportError):
        pass

    # Fallback: walk up from this file looking for pyproject.toml.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            try:
                import tomllib

                data = tomllib.loads(candidate.read_text(encoding="utf-8"))
                return data.get("project", {}).get("version", "unknown")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not parse pyproject.toml: %s", exc)
                break
    return "unknown"


def _capture_pip_freeze() -> list[str]:
    """Return a sorted ``["pkg==version", ...]`` list of installed dists.

    Uses ``importlib.metadata.distributions()`` rather than spawning
    ``pip freeze`` — it's faster, has no subprocess overhead, and works
    in environments where ``pip`` isn't on PATH (e.g. Bazel sandboxes).

    Returns an empty list and logs a warning if metadata enumeration
    fails for any reason.
    """
    try:
        from importlib.metadata import distributions

        seen: set[str] = set()
        items: list[str] = []
        for dist in distributions():
            name = dist.metadata.get("Name") if dist.metadata else None
            if not name:
                continue
            key = name.lower()
            if key in seen:
                # Some environments expose the same dist twice (egg-info +
                # dist-info). Keep the first.
                continue
            seen.add(key)
            items.append(f"{name}=={dist.version}")
        items.sort(key=str.lower)
        return items
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("pip-freeze capture failed: %s", exc)
        return []


def _git(args: list[str], cwd: Path) -> str | None:
    """Run a git subcommand, returning stripped stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git %s failed: %s", " ".join(args), exc)
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _resolve_repo_root() -> Path:
    """Best-effort guess at the repo root for git inspection.

    Walks up from this module looking for a ``.git`` directory; falls
    back to the current working directory if none is found.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def capture_environment() -> dict:
    """Snapshot the execution environment.

    Returns a dict with these keys (all guaranteed present, but values
    may be empty strings or empty lists if a probe failed):

        - ``python_version``: ``sys.version``
        - ``python_implementation``: e.g. ``"CPython"``
        - ``platform``: ``platform.platform()``
        - ``cb_version``: claude-benchmark version
        - ``pip_freeze``: sorted list of installed distributions
        - ``git_commit``: full SHA of HEAD, or ``""``
        - ``git_dirty``: True if working tree has uncommitted changes
        - ``git_branch``: current branch name, or ``""``
    """
    repo_root = _resolve_repo_root()
    git_commit = _git(["rev-parse", "HEAD"], repo_root) or ""
    porcelain = _git(["status", "--porcelain"], repo_root)
    git_dirty = bool(porcelain) if porcelain is not None else False
    git_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root) or ""

    return {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "cb_version": _read_cb_version(),
        "pip_freeze": _capture_pip_freeze(),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "git_branch": git_branch,
    }
