"""Mixed-effects models for nested benchmark data.

The benchmark generates runs nested within (task, model, variant). Treating
runs as independent inflates degrees of freedom and false-positive rates. We
fit a linear mixed model with task as the grouping random effect and model as
an additional random intercept (via a variance components ``vc_formula``) when
data permits. If MixedLM fails to converge we fall back to OLS with
cluster-robust standard errors clustered on task.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FixedEffect:
    """A single fixed-effect row in the model summary."""

    name: str
    coef: float
    std_err: float
    t_value: float
    p_value: float
    ci_low: float
    ci_high: float

    def as_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "coef": self.coef,
            "std_err": self.std_err,
            "t_value": self.t_value,
            "p_value": self.p_value,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
        }


@dataclass
class MixedEffectsResult:
    """Container for a fitted mixed-effects model."""

    method: str
    formula: str
    n_obs: int
    n_groups: int
    fixed_effects: list[FixedEffect] = field(default_factory=list)
    variance_components: dict[str, float] = field(default_factory=dict)
    converged: bool = True
    fallback_reason: str | None = None
    log_likelihood: float | None = None
    aic: float | None = None
    bic: float | None = None

    def fixed_effects_df(self) -> pd.DataFrame:
        return pd.DataFrame([fe.as_dict() for fe in self.fixed_effects])

    def variance_components_df(self) -> pd.DataFrame:
        total = sum(self.variance_components.values()) or float("nan")
        rows = []
        for name, var in self.variance_components.items():
            rows.append(
                {
                    "component": name,
                    "variance": var,
                    "std_dev": float(np.sqrt(var)) if var >= 0 else float("nan"),
                    "share": float(var / total) if total and not np.isnan(total) else float("nan"),
                }
            )
        return pd.DataFrame(rows)


def _build_formula(reference_variant: str) -> str:
    return f"composite ~ C(variant, Treatment(reference='{reference_variant}'))"


def _fixed_effects_from_summary(model_result: Any) -> list[FixedEffect]:
    params = model_result.params
    bse = model_result.bse
    pvalues = model_result.pvalues
    try:
        tvalues = model_result.tvalues
    except AttributeError:
        tvalues = params / bse

    try:
        ci = model_result.conf_int()
        if isinstance(ci, pd.DataFrame):
            ci_low = ci.iloc[:, 0]
            ci_high = ci.iloc[:, 1]
        else:
            ci_low = ci[:, 0]
            ci_high = ci[:, 1]
    except Exception:  # noqa: BLE001
        ci_low = params - 1.96 * bse
        ci_high = params + 1.96 * bse

    out: list[FixedEffect] = []
    for name in params.index:
        out.append(
            FixedEffect(
                name=str(name),
                coef=float(params[name]),
                std_err=float(bse[name]),
                t_value=float(tvalues[name]),
                p_value=float(pvalues[name]),
                ci_low=float(ci_low.loc[name] if hasattr(ci_low, "loc") else ci_low[name]),
                ci_high=float(ci_high.loc[name] if hasattr(ci_high, "loc") else ci_high[name]),
            )
        )
    return out


def _fit_ols_cluster_robust(
    df: pd.DataFrame,
    formula: str,
    *,
    cluster_col: str,
    fallback_reason: str,
) -> MixedEffectsResult:
    import statsmodels.formula.api as smf

    ols_model = smf.ols(formula, data=df)
    ols_fit = ols_model.fit(
        cov_type="cluster",
        cov_kwds={"groups": df[cluster_col].astype(str).to_numpy()},
    )
    fixed = _fixed_effects_from_summary(ols_fit)
    residual_var = float(np.var(ols_fit.resid, ddof=1)) if len(ols_fit.resid) > 1 else float("nan")
    return MixedEffectsResult(
        method=f"OLS+cluster-robust({cluster_col})",
        formula=formula,
        n_obs=int(ols_fit.nobs),
        n_groups=int(df[cluster_col].nunique()),
        fixed_effects=fixed,
        variance_components={"residual": residual_var},
        converged=True,
        fallback_reason=fallback_reason,
        log_likelihood=float(getattr(ols_fit, "llf", float("nan"))),
        aic=float(getattr(ols_fit, "aic", float("nan"))),
        bic=float(getattr(ols_fit, "bic", float("nan"))),
    )


def fit_mixed_effects(
    df: pd.DataFrame,
    *,
    reference_variant: str,
    response: str = "composite",
    group_col: str = "task",
    secondary_group_col: str | None = "model",
) -> MixedEffectsResult:
    """Fit a linear mixed model with random intercepts on ``group_col``.

    Parameters
    ----------
    df
        Tidy run-level DataFrame. Must contain ``response``, ``variant``, and
        ``group_col`` columns.
    reference_variant
        The variant treated as the baseline in the treatment contrast. Must
        appear in ``df['variant']``.
    response
        Outcome column. Defaults to ``"composite"``.
    group_col
        Primary clustering variable for the random intercept. Defaults to
        ``"task"``.
    secondary_group_col
        Optional secondary variance component (e.g. ``"model"``). When provided
        and the column has more than one unique value, a crossed variance
        component is added via ``vc_formula``.
    """
    import statsmodels.formula.api as smf

    if df.empty:
        raise ValueError("DataFrame is empty")
    required = {response, "variant", group_col}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"missing required columns: {sorted(missing)}")

    work = df.dropna(subset=[response, "variant", group_col]).copy()
    if work.empty:
        raise ValueError("no usable rows after dropping NA on response/variant/group_col")

    variants = work["variant"].unique().tolist()
    if reference_variant not in variants:
        raise ValueError(
            f"reference variant '{reference_variant}' not in data; "
            f"available: {variants}"
        )
    if len(variants) < 2:
        raise ValueError("need at least 2 distinct variants to estimate contrasts")

    formula = f"{response} ~ C(variant, Treatment(reference='{reference_variant}'))"

    # Try MixedLM with optional secondary random effect.
    use_secondary = (
        secondary_group_col is not None
        and secondary_group_col in work.columns
        and work[secondary_group_col].nunique() > 1
    )
    vc_formula = None
    re_formula = "1"
    if use_secondary:
        vc_formula = {secondary_group_col: f"0 + C({secondary_group_col})"}

    fallback_reason: str | None = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            md = smf.mixedlm(
                formula,
                data=work,
                groups=work[group_col].astype(str),
                re_formula=re_formula,
                vc_formula=vc_formula,
            )
            mdf = md.fit(method="lbfgs", reml=True, maxiter=200)
        if not getattr(mdf, "converged", True):
            fallback_reason = "MixedLM did not converge"
            raise RuntimeError(fallback_reason)

        fixed = _fixed_effects_from_summary(mdf)
        variance_components: dict[str, float] = {}
        # Group random-intercept variance is in cov_re[0,0].
        try:
            cov_re = np.asarray(mdf.cov_re)
            if cov_re.size:
                variance_components[f"{group_col} (random intercept)"] = float(cov_re[0, 0])
        except Exception:  # noqa: BLE001
            pass
        if use_secondary:
            try:
                vc = mdf.vcomp
                if vc is not None and len(vc):
                    variance_components[
                        f"{secondary_group_col} (variance component)"
                    ] = float(np.asarray(vc).ravel()[0])
            except Exception:  # noqa: BLE001
                pass
        variance_components["residual"] = float(mdf.scale)

        return MixedEffectsResult(
            method="MixedLM (REML)",
            formula=formula,
            n_obs=int(mdf.nobs),
            n_groups=int(work[group_col].nunique()),
            fixed_effects=fixed,
            variance_components=variance_components,
            converged=bool(getattr(mdf, "converged", True)),
            fallback_reason=None,
            log_likelihood=float(getattr(mdf, "llf", float("nan"))),
            aic=float(getattr(mdf, "aic", float("nan"))),
            bic=float(getattr(mdf, "bic", float("nan"))),
        )
    except Exception as exc:  # noqa: BLE001
        if fallback_reason is None:
            fallback_reason = f"MixedLM failed: {exc.__class__.__name__}: {exc}"
        logger.warning("MixedLM fit failed, falling back to OLS+cluster: %s", exc)
        return _fit_ols_cluster_robust(
            work,
            formula,
            cluster_col=group_col,
            fallback_reason=fallback_reason,
        )
