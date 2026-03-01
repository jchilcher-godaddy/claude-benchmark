"""Code diff generation with syntax highlighting for benchmark comparison views.

Uses difflib for unified diffs and Pygments for syntax highlighting.
Produces self-contained HTML with inline styles (no external CSS dependency).
"""

from __future__ import annotations

import difflib
from itertools import combinations

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import DiffLexer


def generate_highlighted_diff(
    code_a: str,
    code_b: str,
    label_a: str = "Profile A",
    label_b: str = "Profile B",
    language: str = "python",
) -> str:
    """Generate a syntax-highlighted unified diff between two code strings.

    Uses Pygments DiffLexer for diff-aware highlighting with inline styles,
    producing self-contained HTML that requires no external CSS.

    Args:
        code_a: Source code from the first profile.
        code_b: Source code from the second profile.
        label_a: Label for the first profile (appears in --- header).
        label_b: Label for the second profile (appears in +++ header).
        language: Programming language hint (unused -- DiffLexer handles all).

    Returns:
        HTML string with syntax-highlighted unified diff,
        or a "no differences" message if the codes are identical.
    """
    diff_lines = list(
        difflib.unified_diff(
            code_a.splitlines(keepends=True),
            code_b.splitlines(keepends=True),
            fromfile=label_a,
            tofile=label_b,
            n=3,
        )
    )

    if not diff_lines:
        return '<p class="no-diff">No differences found.</p>'

    diff_text = "".join(diff_lines)

    lexer = DiffLexer()
    formatter = HtmlFormatter(noclasses=True, style="monokai", nowrap=False)

    return highlight(diff_text, lexer, formatter)


def get_diff_stats(code_a: str, code_b: str) -> dict:
    """Compute diff statistics between two code strings.

    Counts additions, deletions, and unchanged lines in the unified diff.

    Args:
        code_a: Source code from the first profile.
        code_b: Source code from the second profile.

    Returns:
        Dict with keys: additions (int), deletions (int), unchanged (int).
    """
    diff_lines = list(
        difflib.unified_diff(
            code_a.splitlines(keepends=True),
            code_b.splitlines(keepends=True),
            n=3,
        )
    )

    additions = 0
    deletions = 0
    unchanged = 0

    for line in diff_lines:
        # Skip file headers (--- and +++) and hunk headers (@@)
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        elif line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
        elif line.startswith(" "):
            unchanged += 1

    return {
        "additions": additions,
        "deletions": deletions,
        "unchanged": unchanged,
    }


def generate_all_diffs(
    comparison_data: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Generate diffs for all profile pairs across model/task combinations.

    Args:
        comparison_data: Nested dict of {"{model}/{task}": {"{profile_id}": code_output_str}}.
            Each model/task maps to a dict of profile outputs.

    Returns:
        Dict of {"{model}/{task}/{profileA}_vs_{profileB}": highlighted_diff_html}.
        Only distinct pairs are generated (A vs B, not B vs A).
        Pairs where either profile has no code output (empty or None) are skipped.
    """
    result: dict[str, str] = {}

    for model_task, profiles in comparison_data.items():
        profile_ids = sorted(profiles.keys())

        for profile_a, profile_b in combinations(profile_ids, 2):
            code_a = profiles.get(profile_a)
            code_b = profiles.get(profile_b)

            # Skip pairs where either profile has no code output
            if not code_a or not code_b:
                continue

            key = f"{model_task}/{profile_a}_vs_{profile_b}"
            result[key] = generate_highlighted_diff(
                code_a=code_a,
                code_b=code_b,
                label_a=profile_a,
                label_b=profile_b,
            )

    return result
