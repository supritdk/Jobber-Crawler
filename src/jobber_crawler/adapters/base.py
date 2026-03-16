from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ScrapeRequest:
    keywords: list[str]
    location: str | None = None
    filters: dict = field(default_factory=dict)
    max_results: int = 100


@dataclass
class RawJobData:
    source: str
    external_id: str
    raw_data: dict


class BaseScraper(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier, e.g. 'linkedin'."""

    @abstractmethod
    async def scrape(self, request: ScrapeRequest) -> AsyncIterator[RawJobData]:
        """Yield raw job data items from the source."""

    async def health_check(self) -> bool:
        """Return True if the source is reachable."""
        return True
