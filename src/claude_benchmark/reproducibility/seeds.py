"""Deterministic per-run seed derivation.

The Anthropic API does not currently accept a sampling seed, so we cannot
make a temperature-greater-than-zero run bit-exact reproducible against
the model. What we *can* do is record the seed we *would* have used, and
seed every local stochastic component (any retry jittering, padding
selection, sampling helper, etc.) deterministically. That makes the
non-API-side behavior of the harness fully replicable.

The seed for a given run is a deterministic function of:
    - a base experiment seed (configurable; default 42),
    - the experiment id (so different experiments don't collide), and
    - the per-run key (model/profile/task/variant/run-N).
"""

from __future__ import annotations

import hashlib
import logging
import random
from typing import Final

logger = logging.getLogger(__name__)

DEFAULT_BASE_SEED: Final[int] = 42
# 8 bytes = 64-bit unsigned int, well within numpy/random's accepted range.
_SEED_BYTES: Final[int] = 8


def generate_run_seed(
    experiment_id: str,
    run_key: str,
    base_seed: int = DEFAULT_BASE_SEED,
) -> int:
    """Derive a deterministic 64-bit unsigned seed for a single run.

    Args:
        experiment_id: A stable identifier for the experiment (typically
            the experiment name, or ``"<name>-<timestamp>"`` if you want
            seeds to differ between re-runs of the same TOML).
        run_key: The per-run identifier (e.g. ``BenchmarkRun.result_key``,
            which encodes model/profile/task/variant/run-N).
        base_seed: An experiment-wide salt. Change this only if you want
            to draw a fresh random sample without changing any other
            inputs.

    Returns:
        A non-negative integer suitable for ``random.seed()`` and
        ``numpy.random.seed()`` (both accept any non-negative int).
    """
    payload = f"{base_seed}:{experiment_id}:{run_key}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:_SEED_BYTES], byteorder="big", signed=False)


def set_global_seeds(seed: int) -> None:
    """Seed the standard-library and numpy PRNGs.

    NumPy is optional. If it is not installed (or import fails for any
    reason), we silently skip it — this function is designed to be a
    drop-in safety net, not a hard dependency.

    Note: This does NOT seed the model itself. See module docstring.
    """
    random.seed(seed)
    try:
        import numpy as np  # type: ignore[import-not-found]

        # numpy's seed accepts a 32-bit value; mask to be safe.
        np.random.seed(seed & 0xFFFFFFFF)
    except ImportError:
        # numpy is not installed; nothing to seed.
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("numpy seeding failed: %s", exc)
