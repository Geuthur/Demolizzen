# Standard Library
from dataclasses import dataclass


@dataclass
class UniverseName:
    """Represents a universe name returned by ESI."""

    category: str
    id: int
    name: str
