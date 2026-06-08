"""Tests for search provider resolution."""

from siha.config import settings
from siha.tools.search import DuckDuckGoHtmlSearchProvider, get_search_provider


def test_search_provider_falls_back_to_duckduckgo_without_key(monkeypatch):
    monkeypatch.setattr(settings, "search_api_key", "")
    monkeypatch.setattr(settings, "search_provider", "auto")
    assert isinstance(get_search_provider(), DuckDuckGoHtmlSearchProvider)
