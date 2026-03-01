"""Profile loading, discovery, and resolution."""

import logging
from pathlib import Path

import frontmatter

from .errors import ProfileLoadError, ProfileNotFoundError
from .schema import Profile, ProfileMetadata

logger = logging.getLogger(__name__)


def load_profile(profile_path: Path) -> Profile:
    """Load a profile from a .md file with optional YAML frontmatter.

    If the file has YAML frontmatter, it is validated against ProfileMetadata.
    If there is no frontmatter, defaults are generated from the filename.
    The returned Profile.content always has frontmatter stripped.

    Args:
        profile_path: Path to the .md profile file.

    Returns:
        A Profile with validated metadata and stripped content.

    Raises:
        ProfileLoadError: If the file cannot be read or parsed.
    """
    try:
        post = frontmatter.load(str(profile_path))
    except Exception as e:
        raise ProfileLoadError(f"Failed to load profile '{profile_path}': {e}") from e

    try:
        if post.metadata:
            metadata = ProfileMetadata.model_validate(post.metadata)
        else:
            # No frontmatter -- generate defaults from filename
            metadata = ProfileMetadata(
                name=profile_path.stem,
                description=f"Custom profile ({profile_path.name})",
            )
    except Exception as e:
        raise ProfileLoadError(
            f"Invalid frontmatter in '{profile_path}': {e}"
        ) from e

    return Profile(
        path=profile_path,
        metadata=metadata,
        content=post.content,
        slug=profile_path.stem,
    )


def discover_profiles(profiles_dir: Path = Path("profiles")) -> list[Profile]:
    """Discover and load all profiles from the profiles directory.

    Scans for .md files in sorted order. Invalid profiles are skipped
    with a warning logged rather than raising an error.

    Args:
        profiles_dir: Directory containing profile .md files.

    Returns:
        List of valid Profile objects, sorted by filename.
    """
    if not profiles_dir.is_dir():
        return []

    profiles: list[Profile] = []

    for md_file in sorted(profiles_dir.glob("*.md")):
        try:
            profiles.append(load_profile(md_file))
        except (ProfileLoadError, Exception) as e:
            logger.warning("Skipped invalid profile: %s: %s", md_file.name, e)

    return profiles


def resolve_profile(name: str, profiles_dir: Path = Path("profiles")) -> Profile:
    """Resolve a profile name to a loaded Profile object.

    Resolution order:
    1. profiles_dir / "{name}.md" (name without extension)
    2. profiles_dir / name (name with extension)
    3. Path(name) as absolute or relative path

    Args:
        name: Profile name, filename, or path.
        profiles_dir: Directory containing profile .md files.

    Returns:
        The resolved and loaded Profile.

    Raises:
        ProfileNotFoundError: If no matching profile file is found.
    """
    # Try as filename without .md extension
    candidate = profiles_dir / f"{name}.md"
    if candidate.is_file():
        return load_profile(candidate)

    # Try with .md already included
    candidate = profiles_dir / name
    if candidate.is_file():
        return load_profile(candidate)

    # Try as absolute/relative path
    path = Path(name)
    if path.is_file():
        return load_profile(path)

    raise ProfileNotFoundError(
        f"Profile '{name}' not found. "
        f"Looked in: {profiles_dir}/ (as '{name}.md' and '{name}'), "
        f"and as direct path '{name}'."
    )
