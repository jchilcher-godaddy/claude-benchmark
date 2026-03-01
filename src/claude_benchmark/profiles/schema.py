"""Profile metadata schema and Profile data class."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProfileMetadata(BaseModel):
    """YAML frontmatter schema for profile files.

    Validates the metadata extracted from a profile's YAML frontmatter.
    Unknown fields are silently ignored (extra="ignore") so that users
    can add custom frontmatter without causing validation errors.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Human-readable profile name")
    description: str = Field(description="One-line description of what this profile tests")
    variant: Optional[str] = Field(
        default=None,
        description="Profile variant: 'readable', 'compressed', or 'baseline'",
    )
    compressed_from: Optional[str] = Field(
        default=None,
        description="Filename of readable source (for compressed variants)",
    )


@dataclass
class Profile:
    """A loaded benchmark profile.

    Holds the parsed metadata, stripped content (ready for Claude),
    source path, and a slug derived from the filename.
    """

    path: Path
    metadata: ProfileMetadata
    content: str
    slug: str
