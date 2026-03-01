"""Comprehensive integration tests for all 5 prebuilt profiles.

Validates the complete profile suite created across Plans 01, 02, and 03:
- empty (baseline)
- large-readable (readable)
- large-compressed (compressed)
- typical-readable (readable)
- typical-compressed (compressed)
"""

from pathlib import Path

import pytest

from claude_benchmark.profiles import (
    count_tokens_approx,
    discover_profiles,
    load_profile,
)

PROFILES_DIR = Path("profiles")

# Expected profile metadata for parameterized tests
EXPECTED_PROFILES = [
    {
        "path": "profiles/empty.md",
        "name": "empty",
        "variant": "baseline",
        "compressed_from": None,
    },
    {
        "path": "profiles/large-readable.md",
        "name": "large-readable",
        "variant": "readable",
        "compressed_from": None,
    },
    {
        "path": "profiles/large-compressed.md",
        "name": "large-compressed",
        "variant": "compressed",
        "compressed_from": "large-readable.md",
    },
    {
        "path": "profiles/typical-readable.md",
        "name": "typical-readable",
        "variant": "readable",
        "compressed_from": None,
    },
    {
        "path": "profiles/typical-compressed.md",
        "name": "typical-compressed",
        "variant": "compressed",
        "compressed_from": "typical-readable.md",
    },
]

# Language-specific terms that should NOT appear in any profile
LANGUAGE_SPECIFIC_TERMS = [
    "npm",
    "cargo",
    "pip install",
    "go build",
    "javac",
    "rustc",
    "node_modules",
    "package.json",
    "Cargo.toml",
    "pom.xml",
]

# Readable/compressed pairs for compression tests
COMPRESSED_PAIRS = [
    ("profiles/large-readable.md", "profiles/large-compressed.md"),
    ("profiles/typical-readable.md", "profiles/typical-compressed.md"),
]


class TestProfileDiscovery:
    """Tests for discovering the complete profile suite."""

    def test_discovers_exactly_five_profiles(self):
        """discover_profiles() finds all 5 prebuilt profiles."""
        profiles = discover_profiles(PROFILES_DIR)
        assert len(profiles) == 5, (
            f"Expected 5 profiles, found {len(profiles)}: "
            f"{[p.slug for p in profiles]}"
        )

    def test_all_expected_names_present(self):
        """All 5 expected profile names are discovered."""
        profiles = discover_profiles(PROFILES_DIR)
        slugs = {p.slug for p in profiles}
        expected_slugs = {"empty", "large-readable", "large-compressed",
                          "typical-readable", "typical-compressed"}
        assert slugs == expected_slugs

    def test_name_uniqueness(self):
        """All 5 profiles have unique slugs (no duplicates)."""
        profiles = discover_profiles(PROFILES_DIR)
        slugs = [p.slug for p in profiles]
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs found: {slugs}"


class TestVariantDistribution:
    """Tests for correct variant types across profiles."""

    def test_one_baseline(self):
        """Exactly 1 baseline variant exists."""
        profiles = discover_profiles(PROFILES_DIR)
        baselines = [p for p in profiles if p.metadata.variant == "baseline"]
        assert len(baselines) == 1
        assert baselines[0].slug == "empty"

    def test_two_readable(self):
        """Exactly 2 readable variants exist."""
        profiles = discover_profiles(PROFILES_DIR)
        readables = [p for p in profiles if p.metadata.variant == "readable"]
        assert len(readables) == 2
        readable_slugs = {p.slug for p in readables}
        assert readable_slugs == {"large-readable", "typical-readable"}

    def test_two_compressed(self):
        """Exactly 2 compressed variants exist."""
        profiles = discover_profiles(PROFILES_DIR)
        compressed = [p for p in profiles if p.metadata.variant == "compressed"]
        assert len(compressed) == 2
        compressed_slugs = {p.slug for p in compressed}
        assert compressed_slugs == {"large-compressed", "typical-compressed"}


class TestCompressedPairLinkage:
    """Tests for compressed profiles linking back to their readable sources."""

    @pytest.mark.parametrize(
        "readable_path,compressed_path",
        COMPRESSED_PAIRS,
        ids=["large", "typical"],
    )
    def test_compressed_from_is_set(self, readable_path, compressed_path):
        """Compressed profiles have compressed_from set."""
        compressed = load_profile(Path(compressed_path))
        assert compressed.metadata.compressed_from is not None

    @pytest.mark.parametrize(
        "readable_path,compressed_path",
        COMPRESSED_PAIRS,
        ids=["large", "typical"],
    )
    def test_compressed_from_points_to_existing_readable(self, readable_path, compressed_path):
        """compressed_from references an existing readable profile file."""
        compressed = load_profile(Path(compressed_path))
        source_path = PROFILES_DIR / compressed.metadata.compressed_from
        assert source_path.is_file(), (
            f"{compressed.slug} references {compressed.metadata.compressed_from} "
            f"but {source_path} does not exist"
        )

    @pytest.mark.parametrize(
        "readable_path,compressed_path",
        COMPRESSED_PAIRS,
        ids=["large", "typical"],
    )
    def test_compressed_from_matches_readable_slug(self, readable_path, compressed_path):
        """compressed_from filename matches the readable profile's filename."""
        readable = load_profile(Path(readable_path))
        compressed = load_profile(Path(compressed_path))
        expected_filename = f"{readable.slug}.md"
        assert compressed.metadata.compressed_from == expected_filename


class TestEmptyProfile:
    """Tests specific to the empty baseline profile."""

    def test_name_is_empty(self):
        profile = load_profile(Path("profiles/empty.md"))
        assert profile.metadata.name == "empty"

    def test_variant_is_baseline(self):
        profile = load_profile(Path("profiles/empty.md"))
        assert profile.metadata.variant == "baseline"

    def test_content_is_empty(self):
        profile = load_profile(Path("profiles/empty.md"))
        assert profile.content.strip() == ""

    def test_token_count_is_zero(self):
        profile = load_profile(Path("profiles/empty.md"))
        tokens = count_tokens_approx(profile.content)
        assert tokens == 0


class TestLargeProfileSize:
    """Tests for large profile size expectations."""

    def test_large_readable_lines(self):
        """Large readable has 300+ lines."""
        profile = load_profile(Path("profiles/large-readable.md"))
        lines = len(profile.content.strip().split("\n"))
        assert lines >= 300, f"Large readable has only {lines} lines, expected 300+"

    def test_large_readable_tokens(self):
        """Large readable has 1500+ approximate tokens."""
        profile = load_profile(Path("profiles/large-readable.md"))
        tokens = count_tokens_approx(profile.content)
        assert tokens >= 1500, f"Large readable has only {tokens} tokens, expected 1500+"

    def test_large_compressed_fewer_tokens(self):
        """Large compressed has fewer tokens than large readable."""
        readable = load_profile(Path("profiles/large-readable.md"))
        compressed = load_profile(Path("profiles/large-compressed.md"))
        r_tokens = count_tokens_approx(readable.content)
        c_tokens = count_tokens_approx(compressed.content)
        assert c_tokens < r_tokens, (
            f"Compressed ({c_tokens}) not smaller than readable ({r_tokens})"
        )


class TestTypicalProfileSize:
    """Tests for typical profile size expectations."""

    def test_typical_readable_lines(self):
        """Typical readable has 40-200 lines."""
        profile = load_profile(Path("profiles/typical-readable.md"))
        lines = len(profile.content.strip().split("\n"))
        assert 40 <= lines <= 200, (
            f"Typical readable has {lines} lines, expected 40-200"
        )

    def test_typical_readable_tokens(self):
        """Typical readable has 150-800 approximate tokens."""
        profile = load_profile(Path("profiles/typical-readable.md"))
        tokens = count_tokens_approx(profile.content)
        assert 150 <= tokens <= 800, (
            f"Typical readable has {tokens} tokens, expected 150-800"
        )

    def test_typical_compressed_fewer_tokens(self):
        """Typical compressed has fewer tokens than typical readable."""
        readable = load_profile(Path("profiles/typical-readable.md"))
        compressed = load_profile(Path("profiles/typical-compressed.md"))
        r_tokens = count_tokens_approx(readable.content)
        c_tokens = count_tokens_approx(compressed.content)
        assert c_tokens < r_tokens, (
            f"Compressed ({c_tokens}) not smaller than readable ({r_tokens})"
        )


class TestFrontmatterStripped:
    """Tests that frontmatter is properly stripped from profile content."""

    @pytest.mark.parametrize(
        "profile_path",
        [ep["path"] for ep in EXPECTED_PROFILES],
        ids=[ep["name"] for ep in EXPECTED_PROFILES],
    )
    def test_content_does_not_start_with_frontmatter_delimiter(self, profile_path):
        """Profile content does not start with --- (frontmatter was stripped)."""
        profile = load_profile(Path(profile_path))
        content = profile.content.strip()
        if content:  # Skip check for empty profile
            assert not content.startswith("---"), (
                f"{profile.slug} content starts with --- (frontmatter not stripped)"
            )

    @pytest.mark.parametrize(
        "profile_path",
        [ep["path"] for ep in EXPECTED_PROFILES],
        ids=[ep["name"] for ep in EXPECTED_PROFILES],
    )
    def test_content_does_not_have_metadata_as_first_line(self, profile_path):
        """Profile content does not have 'name:' as first non-whitespace line."""
        profile = load_profile(Path(profile_path))
        content = profile.content.strip()
        if content:
            first_line = content.split("\n")[0].strip()
            assert not first_line.startswith("name:"), (
                f"{profile.slug} content starts with 'name:' (metadata not stripped)"
            )


class TestLanguageAgnostic:
    """Tests that all profiles are language-agnostic."""

    @pytest.mark.parametrize(
        "profile_path",
        [ep["path"] for ep in EXPECTED_PROFILES if ep["name"] != "empty"],
        ids=[ep["name"] for ep in EXPECTED_PROFILES if ep["name"] != "empty"],
    )
    def test_no_language_specific_terms(self, profile_path):
        """Non-empty profiles do not contain language-specific terms."""
        profile = load_profile(Path(profile_path))
        content = profile.content.lower()
        found_terms = [term for term in LANGUAGE_SPECIFIC_TERMS if term.lower() in content]
        assert not found_terms, (
            f"{profile.slug} contains language-specific terms: {found_terms}"
        )


class TestLoadEachIndividually:
    """Tests that each profile loads individually with correct metadata."""

    @pytest.mark.parametrize(
        "expected",
        EXPECTED_PROFILES,
        ids=[ep["name"] for ep in EXPECTED_PROFILES],
    )
    def test_load_and_verify_metadata(self, expected):
        """Each profile loads with correct name, variant, and compressed_from."""
        profile = load_profile(Path(expected["path"]))
        assert profile.metadata.name == expected["name"], (
            f"Name mismatch: {profile.metadata.name} != {expected['name']}"
        )
        assert profile.metadata.variant == expected["variant"], (
            f"Variant mismatch for {expected['name']}: "
            f"{profile.metadata.variant} != {expected['variant']}"
        )
        assert profile.metadata.compressed_from == expected["compressed_from"], (
            f"compressed_from mismatch for {expected['name']}: "
            f"{profile.metadata.compressed_from} != {expected['compressed_from']}"
        )


class TestCompressionRatio:
    """Tests for compression ratios between readable/compressed pairs."""

    @pytest.mark.parametrize(
        "readable_path,compressed_path",
        COMPRESSED_PAIRS,
        ids=["large", "typical"],
    )
    def test_compressed_is_smaller(self, readable_path, compressed_path):
        """Compressed version has fewer tokens than readable version."""
        readable = load_profile(Path(readable_path))
        compressed = load_profile(Path(compressed_path))
        r_tokens = count_tokens_approx(readable.content)
        c_tokens = count_tokens_approx(compressed.content)
        assert c_tokens < r_tokens

    @pytest.mark.parametrize(
        "readable_path,compressed_path",
        COMPRESSED_PAIRS,
        ids=["large", "typical"],
    )
    def test_compression_ratio_reported(self, readable_path, compressed_path):
        """Print compression ratio for informational purposes."""
        readable = load_profile(Path(readable_path))
        compressed = load_profile(Path(compressed_path))
        r_tokens = count_tokens_approx(readable.content)
        c_tokens = count_tokens_approx(compressed.content)
        savings_pct = (1 - c_tokens / r_tokens) * 100 if r_tokens > 0 else 0
        print(
            f"\n  {readable.slug}: {r_tokens} tokens -> "
            f"{compressed.slug}: {c_tokens} tokens "
            f"({savings_pct:.1f}% savings)"
        )
        # Informational assertion: at least 15% savings
        assert savings_pct >= 15, (
            f"Compression savings too low: {savings_pct:.1f}% (expected >= 15%)"
        )
