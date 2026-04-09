"""Chart.js 4.x configuration builders for benchmark visualization.

Produces Python dicts that serialize to valid Chart.js JSON configs.
These configs are injected into Jinja2 templates for interactive charts.
"""

from __future__ import annotations

import math

# Human-readable labels for scoring dimensions.
# Used on radar chart axes and comparison table headers.
DIMENSION_LABELS: dict[str, str] = {
    "composite": "Overall",
    "test_pass_rate": "Tests",
    "lint_score": "Lint",
    "complexity_score": "Complexity",
    "llm_quality": "LLM Quality",
    "token_efficiency": "Efficiency",
}


def humanize_dimensions(dimensions: list[str]) -> list[str]:
    """Convert snake_case dimension identifiers to readable labels.

    Uses DIMENSION_LABELS for known dimensions, falls back to title-casing
    with underscores replaced by spaces.
    """
    return [
        DIMENSION_LABELS.get(d, d.replace("_", " ").title())
        for d in dimensions
    ]


# Visually distinct colors suitable for chart datasets (hex strings).
# Works well on both light and dark chart backgrounds.
COLOR_PALETTE: list[str] = [
    "#3b82f6",  # blue
    "#ef4444",  # red
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#06b6d4",  # cyan
    "#84cc16",  # lime
]

# Dash patterns cycled across radar datasets so overlapping lines remain
# distinguishable even when their vertices nearly coincide.
# Chart.js borderDash values: [dash_length, gap_length].
DASH_PATTERNS: list[list[int]] = [
    [],          # solid
    [8, 4],      # dashed
    [2, 3],      # dotted
    [12, 4, 2, 4],  # dash-dot
    [6, 6],      # even dash
    [2, 6],      # wide-spaced dots
    [16, 4],     # long dash
    [4, 4, 2, 4],  # short dash-dot
]


def _get_colors(count: int, colors: list[str] | None = None) -> list[str]:
    """Return a list of colors, cycling through palette if needed."""
    palette = colors if colors else COLOR_PALETTE
    return [palette[i % len(palette)] for i in range(count)]


def _hex_with_alpha(hex_color: str, alpha_hex: str = "33") -> str:
    """Append alpha hex to a 6-digit hex color string.

    Example: _hex_with_alpha("#3b82f6", "33") -> "#3b82f633"
    """
    # Strip existing alpha if 8-digit hex was passed
    base = hex_color[:7] if len(hex_color) > 7 else hex_color
    return f"{base}{alpha_hex}"


def sanitize_chart_data(config: dict) -> dict:
    """Deep-walk the config dict and replace NaN/Inf/-Inf with None.

    Prevents Chart.js from crashing on invalid JSON float values.
    """
    if isinstance(config, dict):
        return {k: sanitize_chart_data(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [sanitize_chart_data(item) for item in config]
    elif isinstance(config, float):
        if math.isnan(config) or math.isinf(config):
            return None
        return config
    return config


def _compute_radar_axis(scores: dict[str, list[float]]) -> tuple[int, int]:
    """Compute dynamic radar axis min and step size based on actual score data.

    When scores cluster in a narrow high range (e.g., 70-90), using a fixed
    0-100 axis wastes most of the chart area. This function raises the axis
    minimum to maximize visual spread between data points.

    Returns:
        (axis_min, step_size) where axis_min is a multiple of 5 and
        step_size evenly divides the range [axis_min, 100].
    """
    # Flatten all scores, filtering out None/NaN/Inf
    all_scores: list[float] = []
    for score_list in scores.values():
        for s in score_list:
            if s is None:
                continue
            if isinstance(s, float) and (math.isnan(s) or math.isinf(s)):
                continue
            all_scores.append(s)

    # No valid data → full range
    if not all_scores:
        return (0, 20)

    min_score = min(all_scores)
    max_score = max(all_scores)
    padding = max(5, math.ceil((max_score - min_score) * 0.15))
    # Round down to nearest 5 (not 10) for finer axis control
    axis_min = int(math.floor((min_score - padding) / 5) * 5)
    axis_min = max(0, axis_min)

    chart_range = 100 - axis_min
    # Use finer step sizes when data clusters tightly
    if chart_range <= 10:
        step_size = 2
    elif chart_range <= 30:
        step_size = 5
    elif chart_range >= 60 and chart_range % 20 == 0:
        step_size = 20
    else:
        step_size = 10

    # Ensure step_size divides chart_range evenly; fall back to 5 then 1
    if chart_range % step_size != 0:
        if chart_range % 5 == 0:
            step_size = 5
        elif chart_range % 2 == 0:
            step_size = 2
        else:
            step_size = 1

    return (axis_min, step_size)


def build_radar_config(
    model_name: str,
    profiles: list[str],
    dimensions: list[str],
    scores: dict[str, list[float]],
    colors: list[str] | None = None,
) -> dict:
    """Build a Chart.js radar config overlaying all profiles for a model.

    Uses actual scores (not per-dimension normalization) so that cross-dimension
    comparisons are accurate — a 76 looks smaller than a 100. When scores cluster
    in a narrow range, the axis minimum is raised above 0 to spread out the
    polygons visually. Tick labels are always shown so the center value is clear.

    Args:
        model_name: Name of the model (used in chart title).
        profiles: List of profile identifiers.
        dimensions: List of dimension labels for the radar axes.
        scores: Mapping of profile -> list of scores (one per dimension).
        colors: Optional custom color list. Defaults to COLOR_PALETTE.

    Returns:
        Chart.js 4.x radar configuration dict.
    """
    palette = _get_colors(len(profiles), colors)
    axis_min, step_size = _compute_radar_axis(scores)

    datasets = []
    for i, profile in enumerate(profiles):
        color = palette[i]
        ds: dict = {
            "label": profile,
            "data": list(scores.get(profile, [0.0] * len(dimensions))),
            "backgroundColor": _hex_with_alpha(color, "33"),
            "borderColor": color,
            "borderWidth": 2,
            "pointRadius": 4,
            "pointHoverRadius": 6,
            "fill": True,
        }
        datasets.append(ds)

    title_text = f"Profile Comparison: {model_name}"
    if axis_min > 0:
        title_text += f"  (center = {axis_min})"

    return sanitize_chart_data({
        "type": "radar",
        "data": {
            "labels": humanize_dimensions(dimensions),
            "datasets": datasets,
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": True,
            "scales": {
                "r": {
                    "min": axis_min,
                    "max": 100,
                    "ticks": {
                        "stepSize": step_size,
                        "display": True,
                    },
                },
            },
            "plugins": {
                "legend": {
                    "position": "top",
                },
                "tooltip": {
                    "enabled": True,
                },
                "title": {
                    "display": True,
                    "text": title_text,
                },
            },
        },
    })


def build_grouped_bar_config(
    dimension: str,
    profiles: list[str],
    tasks: list[str],
    scores: dict[str, dict[str, float]],
    colors: list[str] | None = None,
) -> dict:
    """Build a Chart.js grouped bar config for a dimension's task scores.

    Args:
        dimension: Name of the scoring dimension.
        profiles: List of profile identifiers.
        tasks: List of task names (X-axis labels).
        scores: Mapping of profile -> {task -> score}. Missing tasks default to 0.
        colors: Optional custom color list. Defaults to COLOR_PALETTE.

    Returns:
        Chart.js 4.x bar configuration dict.
    """
    palette = _get_colors(len(profiles), colors)

    datasets = []
    for i, profile in enumerate(profiles):
        profile_scores = scores.get(profile, {})
        datasets.append({
            "label": profile,
            "data": [profile_scores.get(task, 0) for task in tasks],
            "backgroundColor": palette[i],
            "borderColor": palette[i],
            "borderWidth": 1,
        })

    return sanitize_chart_data({
        "type": "bar",
        "data": {
            "labels": tasks,
            "datasets": datasets,
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "scales": {
                "x": {
                    "title": {
                        "display": True,
                        "text": "Task",
                    },
                },
                "y": {
                    "min": 0,
                    "max": 100,
                    "title": {
                        "display": True,
                        "text": "Score",
                    },
                },
            },
            "plugins": {
                "legend": {
                    "position": "top",
                },
                "title": {
                    "display": True,
                    "text": f"Scores by Task: {dimension}",
                },
            },
        },
    })


def build_scatter_with_frontier(
    profiles: list[str],
    token_counts: dict[str, float],
    quality_scores: dict[str, float],
    colors: list[str] | None = None,
) -> dict:
    """Build a Chart.js scatter config with efficient frontier line.

    The efficient frontier connects non-dominated points: profiles that achieve
    the best quality for their token cost level. A point is dominated if another
    point uses fewer tokens and achieves equal or higher quality.

    Args:
        profiles: List of profile identifiers.
        token_counts: Mapping of profile -> token count (X-axis).
        quality_scores: Mapping of profile -> quality score 0-100 (Y-axis).
        colors: Optional custom color list. Defaults to COLOR_PALETTE.

    Returns:
        Chart.js 4.x scatter configuration dict.
    """
    palette = _get_colors(len(profiles), colors)

    # Individual profile datasets as scatter points
    datasets = []
    for i, profile in enumerate(profiles):
        datasets.append({
            "label": profile,
            "data": [{
                "x": token_counts.get(profile, 0),
                "y": quality_scores.get(profile, 0),
            }],
            "backgroundColor": palette[i],
            "borderColor": palette[i],
            "pointRadius": 8,
            "pointHoverRadius": 12,
            "showLine": False,
        })

    # Calculate efficient frontier
    # Sort profiles by token count ascending
    sorted_profiles = sorted(profiles, key=lambda p: token_counts.get(p, 0))

    # Build frontier: keep running max of quality scores
    frontier_points = []
    running_max_quality = -1.0
    for profile in sorted_profiles:
        quality = quality_scores.get(profile, 0)
        tokens = token_counts.get(profile, 0)
        if quality > running_max_quality:
            running_max_quality = quality
            frontier_points.append({"x": tokens, "y": quality})

    # Add frontier line dataset
    if len(frontier_points) >= 2:
        datasets.append({
            "label": "Efficient Frontier",
            "data": frontier_points,
            "borderColor": "#6b7280",
            "borderDash": [5, 5],
            "borderWidth": 2,
            "pointRadius": 0,
            "showLine": True,
            "fill": False,
        })

    return sanitize_chart_data({
        "type": "scatter",
        "data": {
            "datasets": datasets,
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "scales": {
                "x": {
                    "title": {
                        "display": True,
                        "text": "Tokens Consumed",
                    },
                },
                "y": {
                    "min": 0,
                    "max": 100,
                    "title": {
                        "display": True,
                        "text": "Quality Score",
                    },
                },
            },
            "plugins": {
                "legend": {
                    "position": "top",
                },
                "title": {
                    "display": True,
                    "text": "Token Efficiency: Quality vs Cost",
                },
            },
        },
    })


def build_all_chart_configs(
    models: list[str],
    profiles: list[str],
    dimensions: list[str],
    tasks: list[str],
    scores_by_model: dict[str, dict[str, list[float]]],
    scores_by_dimension: dict[str, dict[str, dict[str, float]]],
    token_counts: dict[str, float],
    quality_scores: dict[str, float],
    scores_by_dim_by_model: dict[str, dict[str, dict[str, dict[str, float]]]] | None = None,
    token_counts_by_model: dict[str, dict[str, float]] | None = None,
    quality_scores_by_model: dict[str, dict[str, float]] | None = None,
) -> dict[str, dict]:
    """Build all chart configs for a benchmark report.

    Single entry point that the template renderer uses. Returns a mapping of
    HTML canvas element IDs to their corresponding Chart.js configs.

    When multiple models are present, also produces per-model bar charts
    (``bar-{model}-{dimension}``) and per-model scatter plots
    (``scatter-efficiency-{model}``).

    Args:
        models: List of model names.
        profiles: List of profile identifiers.
        dimensions: List of scoring dimensions.
        tasks: List of task names.
        scores_by_model: {model: {profile: [scores_per_dimension]}}.
        scores_by_dimension: {dimension: {profile: {task: score}}}.
        token_counts: {profile: token_count}.
        quality_scores: {profile: quality_score}.
        scores_by_dim_by_model: {model: {dim: {profile: {task: score}}}}.
        token_counts_by_model: {model: {profile: token_count}}.
        quality_scores_by_model: {model: {profile: quality_score}}.

    Returns:
        Dict mapping canvas IDs to Chart.js config dicts.
        IDs follow pattern: "radar-{model}", "bar-{dimension}", "scatter-efficiency".
        Multi-model adds: "bar-{model}-{dimension}", "scatter-efficiency-{model}".
    """
    configs: dict[str, dict] = {}
    multi_model = len(models) > 1

    # Radar charts: one per model
    for model in models:
        model_scores = scores_by_model.get(model, {})
        canvas_id = f"radar-{model}"
        configs[canvas_id] = build_radar_config(
            model_name=model,
            profiles=profiles,
            dimensions=dimensions,
            scores=model_scores,
        )

    # Grouped bar charts: one per dimension (aggregate across models)
    for dimension in dimensions:
        dim_scores = scores_by_dimension.get(dimension, {})
        canvas_id = f"bar-{dimension}"
        configs[canvas_id] = build_grouped_bar_config(
            dimension=dimension,
            profiles=profiles,
            tasks=tasks,
            scores=dim_scores,
        )

    # Scatter plot: token efficiency (aggregate)
    configs["scatter-efficiency"] = build_scatter_with_frontier(
        profiles=profiles,
        token_counts=token_counts,
        quality_scores=quality_scores,
    )

    # Per-model bar charts when multi-model
    if multi_model and scores_by_dim_by_model:
        for model in models:
            for dimension in dimensions:
                dim_scores = (
                    scores_by_dim_by_model.get(model, {}).get(dimension, {})
                )
                canvas_id = f"bar-{model}-{dimension}"
                configs[canvas_id] = build_grouped_bar_config(
                    dimension=f"{dimension} ({model})",
                    profiles=profiles,
                    tasks=tasks,
                    scores=dim_scores,
                )

    # Per-model scatter plots when multi-model
    if multi_model and token_counts_by_model and quality_scores_by_model:
        for model in models:
            model_tokens = token_counts_by_model.get(model, {})
            model_quality = quality_scores_by_model.get(model, {})
            canvas_id = f"scatter-efficiency-{model}"
            configs[canvas_id] = build_scatter_with_frontier(
                profiles=profiles,
                token_counts=model_tokens,
                quality_scores=model_quality,
            )

    return configs
