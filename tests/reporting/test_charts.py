"""Tests for Chart.js configuration builders."""

from __future__ import annotations

import json
import math

from claude_benchmark.reporting.charts import (
    COLOR_PALETTE,
    DIMENSION_LABELS,
    _compute_radar_axis,
    build_all_chart_configs,
    build_grouped_bar_config,
    build_radar_config,
    build_scatter_with_frontier,
    humanize_dimensions,
    sanitize_chart_data,
)


class TestRadarConfig:
    """Tests for build_radar_config."""

    def test_returns_radar_type(self):
        config = build_radar_config(
            "sonnet", ["a", "b"], ["dim1", "dim2"], {"a": [80, 90], "b": [70, 85]}
        )
        assert config["type"] == "radar"

    def test_correct_number_of_datasets(self):
        config = build_radar_config(
            "sonnet",
            ["profile1", "profile2", "profile3"],
            ["d1", "d2"],
            {"profile1": [80, 90], "profile2": [70, 85], "profile3": [60, 75]},
        )
        assert len(config["data"]["datasets"]) == 3

    def test_correct_scales_single_profile(self):
        """Single profile: dynamic axis min, ticks displayed."""
        config = build_radar_config("sonnet", ["a"], ["d1"], {"a": [80]})
        r_scale = config["options"]["scales"]["r"]
        assert r_scale["max"] == 100
        assert r_scale["ticks"]["display"] is True

    def test_dynamic_axis_multi_profile(self):
        """Multiple profiles: dynamic axis min based on data, ticks shown."""
        config = build_radar_config(
            "sonnet", ["a", "b"], ["d1"], {"a": [90], "b": [80]}
        )
        r_scale = config["options"]["scales"]["r"]
        assert r_scale["max"] == 100
        # Axis min raised above 0 to spread out the data
        assert r_scale["min"] >= 0
        assert r_scale["ticks"]["display"] is True

    def test_dataset_styling(self):
        config = build_radar_config("sonnet", ["a"], ["d1"], {"a": [80]})
        ds = config["data"]["datasets"][0]
        assert ds["borderWidth"] == 2
        assert ds["pointRadius"] == 4
        assert ds["pointHoverRadius"] == 6
        assert ds["fill"] is True

    def test_background_color_has_alpha(self):
        config = build_radar_config("sonnet", ["a"], ["d1"], {"a": [80]})
        bg = config["data"]["datasets"][0]["backgroundColor"]
        assert bg.endswith("33")
        assert len(bg) == 9  # #RRGGBB33

    def test_responsive_and_aspect_ratio(self):
        config = build_radar_config("sonnet", ["a"], ["d1"], {"a": [80]})
        assert config["options"]["responsive"] is True
        assert config["options"]["maintainAspectRatio"] is True

    def test_legend_and_tooltip(self):
        config = build_radar_config("sonnet", ["a"], ["d1"], {"a": [80]})
        assert config["options"]["plugins"]["legend"]["position"] == "top"
        assert config["options"]["plugins"]["tooltip"]["enabled"] is True

    def test_missing_profile_scores_default_to_zeros(self):
        config = build_radar_config(
            "sonnet", ["a", "missing"], ["d1", "d2"], {"a": [80, 90]}
        )
        missing_ds = config["data"]["datasets"][1]
        # Missing profile gets [0, 0] as actual scores
        assert missing_ds["data"] == [0.0, 0.0]
        assert "originalData" not in missing_ds

    def test_fill_enabled(self):
        config = build_radar_config("sonnet", ["a"], ["d1"], {"a": [80]})
        assert config["data"]["datasets"][0]["fill"] is True

    def test_serializable_to_json(self):
        config = build_radar_config(
            "sonnet", ["a", "b"], ["dim1", "dim2"], {"a": [80, 90], "b": [70, 85]}
        )
        # Should not raise
        result = json.dumps(config)
        assert isinstance(result, str)


class TestComputeRadarAxis:
    """Tests for _compute_radar_axis."""

    def test_empty_data_returns_full_range(self):
        assert _compute_radar_axis({}) == (0, 20)

    def test_empty_score_lists_returns_full_range(self):
        assert _compute_radar_axis({"a": []}) == (0, 20)

    def test_low_scores_return_full_range(self):
        """Wide spread with low min naturally lands at axis_min=0."""
        assert _compute_radar_axis({"a": [10, 50, 80]}) == (0, 20)

    def test_zero_score_returns_full_range(self):
        assert _compute_radar_axis({"a": [0, 90]}) == (0, 20)

    def test_high_clustered_scores(self):
        """Scores 75-95 should raise axis min for better spread."""
        axis_min, step_size = _compute_radar_axis({"a": [75, 85, 95]})
        # min=75, spread=20, padding=max(5,ceil(3))=5 → raw=70, mult-of-5=70
        # chart_range = 30 → step_size = 5
        assert axis_min == 70
        assert step_size == 5

    def test_very_high_scores_narrow_range(self):
        """Tightly clustered high scores get a narrow axis."""
        axis_min, step_size = _compute_radar_axis({"a": [92, 95, 98, 100]})
        # min=92, spread=8, padding=max(5,ceil(1.2))=5 → raw=87, mult-of-5=85
        # chart_range = 15 → step_size = 5
        assert axis_min == 85
        assert step_size == 5

    def test_step_size_5_for_tight_range(self):
        """When chart range is 30 or less, step_size should be 5."""
        axis_min, step_size = _compute_radar_axis({"a": [90, 95, 100]})
        # min=90, spread=10, padding=max(5,ceil(1.5))=5 → raw=85, mult-of-5=85
        # chart_range = 15 → step_size = 5
        assert axis_min == 85
        assert step_size == 5
        assert (100 - axis_min) % step_size == 0

    def test_mid_range_scores(self):
        """Scores in 50-80 range."""
        axis_min, step_size = _compute_radar_axis({"a": [50, 60, 70, 80]})
        # min=50, spread=30, padding=max(5,ceil(4.5))=5 → raw=45, mult-of-5=45
        # chart_range = 55 → step_size = 10, but 55%10 != 0 → fall back to 5
        assert axis_min == 45
        assert step_size == 5

    def test_nan_values_filtered(self):
        """NaN values should be ignored, not crash."""
        axis_min, step_size = _compute_radar_axis({"a": [float("nan"), 80, 90]})
        # min=80, spread=10, padding=max(5,ceil(1.5))=5 → raw=75, mult-of-5=75
        assert axis_min == 75
        assert step_size == 5

    def test_none_values_filtered(self):
        """None values should be ignored."""
        axis_min, step_size = _compute_radar_axis({"a": [None, 80, 90]})
        assert axis_min == 75
        assert step_size == 5

    def test_inf_values_filtered(self):
        """Inf values should be ignored."""
        axis_min, step_size = _compute_radar_axis({"a": [float("inf"), 80, 90]})
        assert axis_min == 75
        assert step_size == 5

    def test_axis_min_always_multiple_of_5(self):
        """axis_min should always be a multiple of 5."""
        for min_score in range(0, 100):
            axis_min, _ = _compute_radar_axis({"a": [min_score, 100]})
            assert axis_min % 5 == 0, f"axis_min={axis_min} for min_score={min_score}"

    def test_step_divides_range_evenly(self):
        """step_size should always evenly divide the range."""
        for min_score in range(0, 100):
            axis_min, step_size = _compute_radar_axis({"a": [min_score, 100]})
            chart_range = 100 - axis_min
            assert chart_range % step_size == 0, (
                f"range={chart_range} not divisible by step={step_size} "
                f"for min_score={min_score}"
            )

    def test_tightly_clustered_mid_range(self):
        """Tightly clustered mid-range scores should get a narrow axis, not 0-100."""
        axis_min, step_size = _compute_radar_axis({"a": [60, 62, 65]})
        # min=60, spread=5, padding=max(5,ceil(0.75))=5 → raw=55, mult-of-5=55
        # chart_range = 45 → step_size = 10, but 45%10 != 0 → fall back to 5
        assert axis_min == 55
        assert step_size == 5

    def test_multiple_profiles(self):
        """Considers scores across all profiles."""
        axis_min, step_size = _compute_radar_axis({
            "profile_a": [90, 95],
            "profile_b": [75, 80],
        })
        # min across all is 75, spread=20, padding=max(5,ceil(3))=5 → raw=70, mult-of-5=70
        # chart_range = 30 → step_size = 5
        assert axis_min == 70
        assert step_size == 5

    def test_all_nan_returns_full_range(self):
        """If all values are NaN, treat as empty."""
        assert _compute_radar_axis({"a": [float("nan"), float("nan")]}) == (0, 20)


class TestGroupedBarConfig:
    """Tests for build_grouped_bar_config."""

    def test_returns_bar_type(self):
        config = build_grouped_bar_config(
            "quality", ["a", "b"], ["task1", "task2"], {"a": {"task1": 80, "task2": 90}}
        )
        assert config["type"] == "bar"

    def test_correct_labels(self):
        tasks = ["task1", "task2", "task3"]
        config = build_grouped_bar_config(
            "quality", ["a"], tasks, {"a": {"task1": 80}}
        )
        assert config["data"]["labels"] == tasks

    def test_missing_task_scores_default_to_zero(self):
        config = build_grouped_bar_config(
            "quality",
            ["profile_a"],
            ["task1", "task2", "task3"],
            {"profile_a": {"task1": 80}},  # task2 and task3 missing
        )
        ds = config["data"]["datasets"][0]
        assert ds["data"] == [80, 0, 0]

    def test_y_axis_range(self):
        config = build_grouped_bar_config(
            "quality", ["a"], ["t1"], {"a": {"t1": 50}}
        )
        y_scale = config["options"]["scales"]["y"]
        assert y_scale["min"] == 0
        assert y_scale["max"] == 100

    def test_axis_titles(self):
        config = build_grouped_bar_config(
            "quality", ["a"], ["t1"], {"a": {"t1": 50}}
        )
        assert config["options"]["scales"]["x"]["title"]["text"] == "Task"
        assert config["options"]["scales"]["y"]["title"]["text"] == "Score"

    def test_maintain_aspect_ratio_false(self):
        config = build_grouped_bar_config(
            "quality", ["a"], ["t1"], {"a": {"t1": 50}}
        )
        assert config["options"]["maintainAspectRatio"] is False

    def test_missing_profile_scores(self):
        config = build_grouped_bar_config(
            "quality",
            ["a", "missing"],
            ["t1"],
            {"a": {"t1": 80}},
        )
        missing_ds = config["data"]["datasets"][1]
        assert missing_ds["data"] == [0]


class TestScatterWithFrontier:
    """Tests for build_scatter_with_frontier."""

    def test_returns_scatter_type(self):
        config = build_scatter_with_frontier(
            ["a", "b"], {"a": 100, "b": 200}, {"a": 80, "b": 90}
        )
        assert config["type"] == "scatter"

    def test_profile_point_datasets(self):
        config = build_scatter_with_frontier(
            ["a", "b"], {"a": 100, "b": 200}, {"a": 80, "b": 90}
        )
        # First two datasets are profile points
        assert config["data"]["datasets"][0]["label"] == "a"
        assert config["data"]["datasets"][1]["label"] == "b"
        assert config["data"]["datasets"][0]["pointRadius"] == 8

    def test_frontier_line_present(self):
        config = build_scatter_with_frontier(
            ["a", "b", "c"],
            {"a": 100, "b": 200, "c": 300},
            {"a": 60, "b": 80, "c": 90},
        )
        frontier_ds = config["data"]["datasets"][-1]
        assert frontier_ds["label"] == "Efficient Frontier"
        assert frontier_ds["borderDash"] == [5, 5]
        assert frontier_ds["showLine"] is True
        assert frontier_ds["pointRadius"] == 0

    def test_frontier_excludes_dominated_points(self):
        """A dominated point (high tokens, low quality) should not be on the frontier."""
        config = build_scatter_with_frontier(
            ["efficient", "dominated", "best"],
            {"efficient": 100, "dominated": 200, "best": 300},
            {"efficient": 80, "dominated": 70, "best": 90},  # dominated has lower quality despite more tokens
        )
        frontier_ds = config["data"]["datasets"][-1]
        frontier_x_values = [pt["x"] for pt in frontier_ds["data"]]
        # "dominated" at x=200, y=70 should not appear (efficient at x=100 has y=80 which is higher)
        assert 200 not in frontier_x_values
        # efficient (100, 80) and best (300, 90) should be on frontier
        assert 100 in frontier_x_values
        assert 300 in frontier_x_values

    def test_frontier_with_single_point_no_line(self):
        """With only one profile, no frontier line is generated (need >= 2 points)."""
        config = build_scatter_with_frontier(
            ["a"], {"a": 100}, {"a": 80}
        )
        # Only the profile dataset, no frontier
        assert len(config["data"]["datasets"]) == 1

    def test_axis_labels(self):
        config = build_scatter_with_frontier(
            ["a", "b"], {"a": 100, "b": 200}, {"a": 80, "b": 90}
        )
        assert config["options"]["scales"]["x"]["title"]["text"] == "Tokens Consumed"
        assert config["options"]["scales"]["y"]["title"]["text"] == "Quality Score"


class TestColorPalette:
    """Tests for COLOR_PALETTE and color cycling."""

    def test_palette_has_minimum_colors(self):
        assert len(COLOR_PALETTE) >= 8

    def test_colors_are_hex(self):
        for color in COLOR_PALETTE:
            assert color.startswith("#")
            assert len(color) == 7  # #RRGGBB

    def test_cycling_when_more_profiles_than_colors(self):
        # Create more profiles than colors in palette
        many_profiles = [f"p{i}" for i in range(len(COLOR_PALETTE) + 3)]
        dimensions = ["d1"]
        scores = {p: [50.0] for p in many_profiles}
        config = build_radar_config("test", many_profiles, dimensions, scores)
        # Should not error, and datasets should cycle colors
        assert len(config["data"]["datasets"]) == len(many_profiles)
        # First and (first + palette_length) should have same color
        ds_0_color = config["data"]["datasets"][0]["borderColor"]
        ds_cycle_color = config["data"]["datasets"][len(COLOR_PALETTE)]["borderColor"]
        assert ds_0_color == ds_cycle_color


class TestSanitizeChartData:
    """Tests for sanitize_chart_data."""

    def test_replaces_nan_with_none(self):
        result = sanitize_chart_data({"value": float("nan")})
        assert result["value"] is None

    def test_replaces_inf_with_none(self):
        result = sanitize_chart_data({"value": float("inf")})
        assert result["value"] is None

    def test_replaces_negative_inf_with_none(self):
        result = sanitize_chart_data({"value": float("-inf")})
        assert result["value"] is None

    def test_preserves_normal_floats(self):
        result = sanitize_chart_data({"value": 42.5})
        assert result["value"] == 42.5

    def test_deep_walks_nested_structure(self):
        config = {
            "data": {
                "datasets": [
                    {"data": [1.0, float("nan"), 3.0]},
                ],
            },
        }
        result = sanitize_chart_data(config)
        assert result["data"]["datasets"][0]["data"] == [1.0, None, 3.0]

    def test_preserves_strings_and_bools(self):
        config = {"type": "radar", "responsive": True, "count": 5}
        result = sanitize_chart_data(config)
        assert result == config

    def test_handles_empty_dict(self):
        assert sanitize_chart_data({}) == {}


class TestBuildAllChartConfigs:
    """Tests for build_all_chart_configs."""

    def test_returns_expected_canvas_ids(self):
        configs = build_all_chart_configs(
            models=["sonnet", "opus"],
            profiles=["minimal", "full"],
            dimensions=["quality", "speed"],
            tasks=["task1"],
            scores_by_model={
                "sonnet": {"minimal": [80, 70], "full": [90, 85]},
                "opus": {"minimal": [85, 75], "full": [95, 90]},
            },
            scores_by_dimension={
                "quality": {"minimal": {"task1": 80}, "full": {"task1": 90}},
                "speed": {"minimal": {"task1": 70}, "full": {"task1": 85}},
            },
            token_counts={"minimal": 100, "full": 500},
            quality_scores={"minimal": 80, "full": 90},
        )
        expected_keys = {
            "radar-sonnet",
            "radar-opus",
            "bar-quality",
            "bar-speed",
            "scatter-efficiency",
        }
        assert set(configs.keys()) == expected_keys

    def test_all_configs_are_dicts(self):
        configs = build_all_chart_configs(
            models=["sonnet"],
            profiles=["a"],
            dimensions=["quality"],
            tasks=["task1"],
            scores_by_model={"sonnet": {"a": [80]}},
            scores_by_dimension={"quality": {"a": {"task1": 80}}},
            token_counts={"a": 100},
            quality_scores={"a": 80},
        )
        for canvas_id, config in configs.items():
            assert isinstance(config, dict), f"Config for {canvas_id} is not a dict"

    def test_all_configs_serializable(self):
        configs = build_all_chart_configs(
            models=["sonnet"],
            profiles=["a"],
            dimensions=["quality"],
            tasks=["task1"],
            scores_by_model={"sonnet": {"a": [80]}},
            scores_by_dimension={"quality": {"a": {"task1": 80}}},
            token_counts={"a": 100},
            quality_scores={"a": 80},
        )
        # All configs should be JSON-serializable
        result = json.dumps(configs)
        assert isinstance(result, str)


class TestHumanizeDimensions:
    """Tests for DIMENSION_LABELS and humanize_dimensions."""

    def test_known_dimensions_mapped(self):
        dims = ["composite", "test_pass_rate", "lint_score"]
        result = humanize_dimensions(dims)
        assert result == ["Overall", "Tests", "Lint"]

    def test_all_known_labels(self):
        dims = list(DIMENSION_LABELS.keys())
        result = humanize_dimensions(dims)
        assert result == list(DIMENSION_LABELS.values())

    def test_unknown_dimension_fallback(self):
        result = humanize_dimensions(["some_new_metric"])
        assert result == ["Some New Metric"]

    def test_mixed_known_and_unknown(self):
        result = humanize_dimensions(["composite", "custom_score", "lint_score"])
        assert result == ["Overall", "Custom Score", "Lint"]

    def test_empty_list(self):
        assert humanize_dimensions([]) == []

    def test_radar_config_uses_humanized_labels(self):
        """build_radar_config should output humanized labels, not raw dimension IDs."""
        config = build_radar_config(
            "sonnet",
            ["a"],
            ["test_pass_rate", "lint_score", "complexity_score"],
            {"a": [80, 90, 70]},
        )
        labels = config["data"]["labels"]
        assert labels == ["Tests", "Lint", "Complexity"]


class TestRadarConfigScoring:
    """Tests for radar chart using actual scores (no normalization)."""

    def test_actual_scores_in_radar_config(self):
        config = build_radar_config(
            "test", ["a", "b"], ["d1"], {"a": [90.2], "b": [91.0]}
        )
        ds_a = config["data"]["datasets"][0]
        # No normalization — actual scores used directly
        assert "originalData" not in ds_a
        assert ds_a["data"] == [90.2]

    def test_title_indicates_center_when_raised(self):
        config = build_radar_config(
            "opus", ["a", "b"], ["d1"], {"a": [90], "b": [95]}
        )
        title = config["options"]["plugins"]["title"]["text"]
        r_min = config["options"]["scales"]["r"]["min"]
        if r_min > 0:
            assert f"center = {r_min}" in title
