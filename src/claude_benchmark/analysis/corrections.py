"""Multiple-comparisons corrections (Holm-Bonferroni and Benjamini-Hochberg)."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


def _holm_bonferroni(p_values: np.ndarray) -> np.ndarray:
    """Holm step-down Bonferroni adjustment.

    For each p-value sorted ascending, multiply by ``(m - rank)`` and enforce
    monotonicity (a later adjusted value never exceeds an earlier one read
    from the front).
    """
    m = p_values.size
    if m == 0:
        return np.array([], dtype=float)
    order = np.argsort(p_values, kind="mergesort")
    sorted_p = p_values[order]
    adjusted = sorted_p * (m - np.arange(m))
    # Enforce monotonic non-decreasing along the sorted order.
    np.maximum.accumulate(adjusted, out=adjusted)
    adjusted = np.clip(adjusted, 0.0, 1.0)
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out


def _benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR adjustment.

    Sort ascending, compute ``p * m / rank`` (1-indexed rank), enforce
    monotonic non-increasing from the largest rank backward, then clip to
    ``[0, 1]``.
    """
    m = p_values.size
    if m == 0:
        return np.array([], dtype=float)
    order = np.argsort(p_values, kind="mergesort")
    sorted_p = p_values[order]
    ranks = np.arange(1, m + 1)
    adjusted = sorted_p * m / ranks
    # Enforce monotonic non-increasing from the back so smaller-rank adjusted
    # values are never larger than later ones (BH "step-up").
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out


def correct_pvalues(
    p_values: Mapping[str, float],
    *,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Apply Holm-Bonferroni and Benjamini-Hochberg corrections.

    Parameters
    ----------
    p_values
        Mapping of contrast name to raw p-value (float in ``[0, 1]``).
    alpha
        Family-wise / FDR error rate used to flag significance. Default 0.05.

    Returns
    -------
    DataFrame
        Columns: ``contrast``, ``p_raw``, ``p_holm``, ``p_bh``,
        ``sig_raw``, ``sig_holm``, ``sig_bh``. Sorted by raw p ascending.
    """
    if not p_values:
        return pd.DataFrame(
            columns=["contrast", "p_raw", "p_holm", "p_bh", "sig_raw", "sig_holm", "sig_bh"],
        )
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1); got {alpha}")

    names = list(p_values.keys())
    raw = np.array([float(p_values[n]) for n in names], dtype=float)
    if np.any((raw < 0) | (raw > 1) | np.isnan(raw)):
        raise ValueError("p-values must be finite floats in [0, 1]")

    holm = _holm_bonferroni(raw)
    bh = _benjamini_hochberg(raw)

    df = pd.DataFrame(
        {
            "contrast": names,
            "p_raw": raw,
            "p_holm": holm,
            "p_bh": bh,
            "sig_raw": raw < alpha,
            "sig_holm": holm < alpha,
            "sig_bh": bh < alpha,
        }
    )
    df = df.sort_values("p_raw", kind="mergesort").reset_index(drop=True)
    return df
