from abc import ABC, abstractmethod

from ..adapters.base import RawJobData
from ..schemas.job import ScrapedJobCreate


class BaseFieldMapper(ABC):
    """Maps source-specific raw data to the unified ScrapedJobCreate schema."""

    @abstractmethod
    def map(self, raw: RawJobData) -> ScrapedJobCreate:
        """Transform raw source data into the canonical schema."""

    @staticmethod
    def safe_get(data: dict, *keys, default=None):
        """Nested dict access with fallback."""
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, default)
            else:
                return default
        return current
