"""Profile-related exception classes."""


class ProfileLoadError(Exception):
    """Raised when a profile file cannot be loaded.

    This covers cases like missing files, invalid frontmatter,
    file permission errors, etc.
    """

    pass


class ProfileNotFoundError(Exception):
    """Raised when a profile name cannot be resolved to a file.

    This is raised by resolve_profile() when no matching file
    is found in the profiles directory or as a direct path.
    """

    pass
