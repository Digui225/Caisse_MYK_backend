"""Fournisseurs FNE : API réelle (`api`), simulée (`mock`) ou aucun (`manual`)."""

from functools import lru_cache

from caisse.config import get_settings
from caisse.domain.ports import FneProvider
from caisse.infrastructure.fne.http_client import HttpFneProvider
from caisse.infrastructure.fne.mock import MockFneProvider

__all__ = ["HttpFneProvider", "MockFneProvider", "get_fne_provider"]


@lru_cache
def get_fne_provider() -> FneProvider | None:
    settings = get_settings()
    if settings.fne_provider == "api":
        return HttpFneProvider(settings.fne_api_base_url, settings.fne_api_key)
    if settings.fne_provider == "mock":
        return MockFneProvider()
    return None
