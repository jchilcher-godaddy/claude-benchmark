"""Profile management for claude-benchmark.

Provides loading, discovery, resolution, and token counting for
CLAUDE.md benchmark profiles stored as .md files with YAML frontmatter.
"""

from .errors import ProfileLoadError, ProfileNotFoundError
from .loader import discover_profiles, load_profile, resolve_profile
from .schema import Profile, ProfileMetadata
from .token_counter import count_tokens, count_tokens_approx

__all__ = [
    "Profile",
    "ProfileLoadError",
    "ProfileMetadata",
    "ProfileNotFoundError",
    "count_tokens",
    "count_tokens_approx",
    "discover_profiles",
    "load_profile",
    "resolve_profile",
]
