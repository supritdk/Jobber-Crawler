from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseScraper

_ADAPTERS: dict[str, type[BaseScraper]] = {}
_MAPPERS: dict[str, type] = {}


def register_adapter(name: str):
    """Decorator to register a scraper adapter."""

    def wrapper(cls):
        _ADAPTERS[name] = cls
        return cls

    return wrapper


def register_mapper(name: str):
    """Decorator to register a field mapper."""

    def wrapper(cls):
        _MAPPERS[name] = cls
        return cls

    return wrapper


def get_adapter(name: str, **kwargs) -> BaseScraper:
    if name not in _ADAPTERS:
        raise ValueError(f"Unknown adapter: {name}. Available: {list(_ADAPTERS.keys())}")
    return _ADAPTERS[name](**kwargs)


def get_mapper(name: str, **kwargs):
    if name not in _MAPPERS:
        raise ValueError(f"Unknown mapper: {name}. Available: {list(_MAPPERS.keys())}")
    return _MAPPERS[name](**kwargs)


def list_adapters() -> list[str]:
    return list(_ADAPTERS.keys())
