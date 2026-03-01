"""Tests for code diff generation with syntax highlighting."""

from __future__ import annotations

from claude_benchmark.reporting.diff_view import (
    generate_all_diffs,
    generate_highlighted_diff,
    get_diff_stats,
)


class TestGenerateHighlightedDiff:
    """Tests for generate_highlighted_diff."""

    def test_produces_html_with_pygments_markup(self):
        code_a = "def hello():\n    print('hello')\n"
        code_b = "def hello():\n    print('world')\n"
        result = generate_highlighted_diff(code_a, code_b)
        # Should contain Pygments-generated HTML (inline styles)
        assert "<div" in result or "<pre" in result or "<span" in result
        assert "style=" in result

    def test_identical_code_returns_no_diff_message(self):
        code = "def hello():\n    print('hello')\n"
        result = generate_highlighted_diff(code, code)
        assert "No differences found" in result
        assert 'class="no-diff"' in result

    def test_output_contains_diff_markers(self):
        code_a = "line1\nline2\n"
        code_b = "line1\nchanged\n"
        result = generate_highlighted_diff(code_a, code_b)
        # The rendered HTML should contain the --- and +++ markers visually
        assert "---" in result
        assert "+++" in result

    def test_labels_appear_in_output(self):
        code_a = "old\n"
        code_b = "new\n"
        result = generate_highlighted_diff(
            code_a, code_b, label_a="baseline", label_b="optimized"
        )
        assert "baseline" in result
        assert "optimized" in result

    def test_multiline_diff(self):
        code_a = "line1\nline2\nline3\nline4\n"
        code_b = "line1\nmodified\nline3\nadded\nline4\n"
        result = generate_highlighted_diff(code_a, code_b)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_code_a(self):
        result = generate_highlighted_diff("", "new code\n")
        # Should show additions
        assert "new code" in result

    def test_empty_code_b(self):
        result = generate_highlighted_diff("old code\n", "")
        # Should show deletions
        assert "old code" in result


class TestGetDiffStats:
    """Tests for get_diff_stats."""

    def test_counts_additions_correctly(self):
        code_a = "line1\n"
        code_b = "line1\nline2\n"
        stats = get_diff_stats(code_a, code_b)
        assert stats["additions"] == 1

    def test_counts_deletions_correctly(self):
        code_a = "line1\nline2\n"
        code_b = "line1\n"
        stats = get_diff_stats(code_a, code_b)
        assert stats["deletions"] == 1

    def test_counts_unchanged_correctly(self):
        code_a = "line1\nline2\nline3\n"
        code_b = "line1\nchanged\nline3\n"
        stats = get_diff_stats(code_a, code_b)
        # line1 and line3 are context (unchanged)
        assert stats["unchanged"] >= 2

    def test_identical_code_has_zero_changes(self):
        code = "same\n"
        stats = get_diff_stats(code, code)
        assert stats["additions"] == 0
        assert stats["deletions"] == 0
        assert stats["unchanged"] == 0  # no diff generated at all

    def test_returns_correct_keys(self):
        stats = get_diff_stats("a\n", "b\n")
        assert "additions" in stats
        assert "deletions" in stats
        assert "unchanged" in stats

    def test_modification_counts_both_add_and_delete(self):
        code_a = "old line\n"
        code_b = "new line\n"
        stats = get_diff_stats(code_a, code_b)
        # A modification is a deletion + addition
        assert stats["additions"] >= 1
        assert stats["deletions"] >= 1


class TestGenerateAllDiffs:
    """Tests for generate_all_diffs."""

    def test_produces_correct_keys_for_profile_pairs(self):
        data = {
            "sonnet/task1": {
                "minimal": "code a\n",
                "full": "code b\n",
                "compressed": "code c\n",
            }
        }
        result = generate_all_diffs(data)
        # With 3 profiles, expect C(3,2) = 3 pairs
        # Sorted: compressed, full, minimal -> pairs: c_vs_f, c_vs_m, f_vs_m
        expected_keys = {
            "sonnet/task1/compressed_vs_full",
            "sonnet/task1/compressed_vs_minimal",
            "sonnet/task1/full_vs_minimal",
        }
        assert set(result.keys()) == expected_keys

    def test_skips_empty_code_outputs(self):
        data = {
            "sonnet/task1": {
                "minimal": "code a\n",
                "full": "",  # empty
            }
        }
        result = generate_all_diffs(data)
        assert len(result) == 0

    def test_skips_none_code_outputs(self):
        data = {
            "sonnet/task1": {
                "minimal": "code a\n",
                "full": None,
            }
        }
        result = generate_all_diffs(data)
        assert len(result) == 0

    def test_multiple_model_task_combos(self):
        data = {
            "sonnet/task1": {
                "a": "code 1\n",
                "b": "code 2\n",
            },
            "opus/task1": {
                "a": "code 3\n",
                "b": "code 4\n",
            },
        }
        result = generate_all_diffs(data)
        assert "sonnet/task1/a_vs_b" in result
        assert "opus/task1/a_vs_b" in result

    def test_all_values_are_html_strings(self):
        data = {
            "sonnet/task1": {
                "a": "line1\n",
                "b": "line2\n",
            },
        }
        result = generate_all_diffs(data)
        for key, html in result.items():
            assert isinstance(html, str), f"Value for {key} is not a string"
            # Should contain HTML markup or no-diff message
            assert "<" in html

    def test_single_profile_produces_no_diffs(self):
        data = {
            "sonnet/task1": {
                "only_profile": "some code\n",
            }
        }
        result = generate_all_diffs(data)
        assert len(result) == 0

    def test_identical_profiles_produce_no_diff_message(self):
        same_code = "identical code\n"
        data = {
            "sonnet/task1": {
                "a": same_code,
                "b": same_code,
            }
        }
        result = generate_all_diffs(data)
        assert "sonnet/task1/a_vs_b" in result
        assert "No differences found" in result["sonnet/task1/a_vs_b"]
