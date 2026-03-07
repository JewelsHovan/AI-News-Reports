from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchResult:
    """Result from a single news source fetch operation."""

    source: str
    items: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    items_found: int = 0

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "items_found": self.items_found,
            "items": self.items,
            "metadata": self.metadata,
            "error": self.error,
        }
