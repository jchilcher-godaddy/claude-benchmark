"""Comprehensive tests for the profile management system."""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from claude_benchmark.cli.main import app
from claude_benchmark.profiles.errors import ProfileLoadError, ProfileNotFoundError
from claude_benchmark.profiles.loader import discover_profiles, load_profile, resolve_profile
from claude_benchmark.profiles.schema import Profile, ProfileMetadata
from claude_benchmark.profiles.token_counter import count_tokens, count_tokens_approx

runner = CliRunner()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestProfileMetadata:
    def test_validates_with_name_and_description(self):
        meta = ProfileMetadata(name="test", description="A test profile")
        assert meta.name == "test"
        assert meta.description == "A test profile"
        assert meta.variant is None
        assert meta.compressed_from is None

    def test_validates_with_all_optional_fields(self):
        meta = ProfileMetadata(
            name="large-compressed",
            description="Compressed large profile",
            variant="compressed",
            compressed_from="large-readable.md",
        )
        assert meta.variant == "compressed"
        assert meta.compressed_from == "large-readable.md"

    def test_ignores_unknown_extra_fields(self):
        meta = ProfileMetadata.model_validate(
            {
                "name": "test",
                "description": "A test",
                "unknown_field": "should be ignored",
                "another_extra": 42,
            }
        )
        assert meta.name == "test"
        assert not hasattr(meta, "unknown_field")

    def test_rejects_missing_name(self):
        with pytest.raises(ValidationError):
            ProfileMetadata(description="No name given")

    def test_rejects_missing_description(self):
        with pytest.raises(ValidationError):
            ProfileMetadata(name="no-desc")


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------


class TestLoadProfile:
    def test_with_frontmatter(self, tmp_path):
        profile_file = tmp_path / "test.md"
        profile_file.write_text(
            "---\n"
            "name: test-profile\n"
            "description: A test profile\n"
            "variant: readable\n"
            "---\n"
            "\n"
            "# Instructions\n"
            "\n"
            "Do something useful.\n"
        )
        profile = load_profile(profile_file)
        assert profile.metadata.name == "test-profile"
        assert profile.metadata.description == "A test profile"
        assert profile.metadata.variant == "readable"
        assert "# Instructions" in profile.content
        assert "Do something useful." in profile.content
        # Frontmatter must be stripped from content
        assert "---" not in profile.content
        assert profile.slug == "test"
        assert profile.path == profile_file

    def test_without_frontmatter(self, tmp_path):
        profile_file = tmp_path / "my-custom.md"
        profile_file.write_text("# My Custom Config\n\nUse snake_case.\n")
        profile = load_profile(profile_file)
        assert profile.metadata.name == "my-custom"
        assert "Custom profile" in profile.metadata.description
        assert "# My Custom Config" in profile.content
        assert "Use snake_case." in profile.content

    def test_empty_profile_frontmatter_only(self, tmp_path):
        profile_file = tmp_path / "empty.md"
        profile_file.write_text(
            "---\n"
            "name: empty\n"
            "description: Empty baseline\n"
            "variant: baseline\n"
            "---\n"
        )
        profile = load_profile(profile_file)
        assert profile.metadata.name == "empty"
        assert profile.content.strip() == ""

    def test_load_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(ProfileLoadError):
            load_profile(tmp_path / "nonexistent.md")


class TestDiscoverProfiles:
    def test_finds_all_md_files(self, tmp_path):
        (tmp_path / "alpha.md").write_text("---\nname: alpha\ndescription: Alpha\n---\n")
        (tmp_path / "beta.md").write_text("---\nname: beta\ndescription: Beta\n---\n")
        (tmp_path / "not-a-profile.txt").write_text("ignore me")
        profiles = discover_profiles(tmp_path)
        assert len(profiles) == 2
        slugs = [p.slug for p in profiles]
        assert slugs == ["alpha", "beta"]  # sorted order

    def test_returns_empty_for_nonexistent_directory(self, tmp_path):
        profiles = discover_profiles(tmp_path / "does-not-exist")
        assert profiles == []

    def test_skips_invalid_files_and_logs_warning(self, tmp_path, caplog):
        # Valid profile
        (tmp_path / "good.md").write_text("---\nname: good\ndescription: Good\n---\n")
        # Invalid profile: frontmatter with missing required field
        (tmp_path / "bad.md").write_text("---\nname: bad\n---\n")
        with caplog.at_level(logging.WARNING):
            profiles = discover_profiles(tmp_path)
        assert len(profiles) == 1
        assert profiles[0].slug == "good"
        assert "bad.md" in caplog.text


class TestResolveProfile:
    def test_by_name_without_extension(self, tmp_path):
        (tmp_path / "large-readable.md").write_text(
            "---\nname: large-readable\ndescription: Large\n---\nContent here."
        )
        profile = resolve_profile("large-readable", tmp_path)
        assert profile.metadata.name == "large-readable"

    def test_by_name_with_extension(self, tmp_path):
        (tmp_path / "typical.md").write_text(
            "---\nname: typical\ndescription: Typical\n---\nContent."
        )
        profile = resolve_profile("typical.md", tmp_path)
        assert profile.metadata.name == "typical"

    def test_raises_for_missing_profile(self, tmp_path):
        with pytest.raises(ProfileNotFoundError, match="not-here"):
            resolve_profile("not-here", tmp_path)


# ---------------------------------------------------------------------------
# Token counter tests
# ---------------------------------------------------------------------------


class TestTokenCounter:
    def test_approx_400_chars_returns_100(self):
        assert count_tokens_approx("x" * 400) == 100

    def test_approx_empty_string_returns_0(self):
        assert count_tokens_approx("") == 0

    def test_approx_short_string_returns_at_least_1(self):
        assert count_tokens_approx("hi") >= 1

    def test_count_tokens_no_api_returns_approximate(self):
        count, is_exact = count_tokens("x" * 400, use_api=False)
        assert count == 100
        assert is_exact is False

    def test_count_tokens_empty_string_returns_zero_exact(self):
        count, is_exact = count_tokens("", use_api=False)
        assert count == 0
        assert is_exact is True

    def test_count_tokens_whitespace_only_returns_zero_exact(self):
        count, is_exact = count_tokens("   \n\t  ", use_api=False)
        assert count == 0
        assert is_exact is True


# ---------------------------------------------------------------------------
# Empty profile integration tests
# ---------------------------------------------------------------------------


class TestEmptyProfile:
    def test_load_empty_profile(self):
        profile = load_profile(Path("profiles/empty.md"))
        assert profile.metadata.name == "empty"

    def test_empty_profile_variant(self):
        profile = load_profile(Path("profiles/empty.md"))
        assert profile.metadata.variant == "baseline"

    def test_empty_profile_content_is_empty(self):
        profile = load_profile(Path("profiles/empty.md"))
        assert profile.content.strip() == ""


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLIProfiles:
    def test_profiles_help(self):
        result = runner.invoke(app, ["profiles", "--help"])
        assert result.exit_code == 0
        assert "profiles" in result.output.lower() or "List" in result.output

    def test_profiles_lists_table(self):
        result = runner.invoke(app, ["profiles"])
        assert result.exit_code == 0
        assert "empty" in result.output
        assert "Available Profiles" in result.output

    def test_profiles_empty_directory_exits_error(self, tmp_path):
        empty_dir = tmp_path / "empty_profiles"
        empty_dir.mkdir()
        result = runner.invoke(app, ["profiles", "--profiles-dir", str(empty_dir)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Custom profile (PROF-06) tests
# ---------------------------------------------------------------------------


class TestCustomProfile:
    def test_discover_finds_custom_no_frontmatter(self, tmp_path):
        custom = tmp_path / "my-config.md"
        custom.write_text("# My Config\n\nUse consistent naming.\nPrefer explicit imports.\n")
        profiles = discover_profiles(tmp_path)
        assert len(profiles) == 1
        assert profiles[0].slug == "my-config"

    def test_custom_has_filename_based_name(self, tmp_path):
        custom = tmp_path / "team-rules.md"
        custom.write_text("Always run tests before committing.\n")
        profile = load_profile(custom)
        assert profile.metadata.name == "team-rules"
        assert "Custom profile" in profile.metadata.description

    def test_custom_content_fully_preserved(self, tmp_path):
        content = "# Full Content\n\nLine 1.\nLine 2.\nLine 3.\n"
        custom = tmp_path / "raw.md"
        custom.write_text(content)
        profile = load_profile(custom)
        # python-frontmatter strips trailing newlines from content
        assert profile.content == content.rstrip("\n")
