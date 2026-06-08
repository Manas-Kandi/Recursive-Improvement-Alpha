"""Search provider abstraction used by web_search."""

import html
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from siha.config import settings


class SearchProvider(ABC):
    """Interface for web search providers."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        pass


class TavilySearchProvider(SearchProvider):
    """Tavily search provider."""

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.search_api_key,
                "query": query,
                "max_results": max_results,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("results", [])


class BraveSearchProvider(SearchProvider):
    """Brave Search API provider."""

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": settings.search_api_key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        web_results = payload.get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("description", ""),
            }
            for r in web_results
        ]


class DuckDuckGoHtmlSearchProvider(SearchProvider):
    """No-key fallback search provider using DuckDuckGo's HTML endpoint."""

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "SIHA-Agent/0.1"},
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        body = resp.text
        matches = re.findall(
            r'<a rel="nofollow" class="result__a" href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
            r'<a class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            body,
            re.S,
        )
        results: List[Dict[str, Any]] = []
        for url, title, snippet in matches[:max_results]:
            clean_title = re.sub(r"<[^>]+>", "", title)
            clean_snippet = re.sub(r"<[^>]+>", "", snippet)
            results.append(
                {
                    "title": html.unescape(clean_title).strip(),
                    "url": html.unescape(url).strip(),
                    "content": html.unescape(clean_snippet).strip(),
                }
            )
        return results


def get_search_provider() -> SearchProvider:
    """Resolve the configured search provider."""
    if settings.search_provider == "duckduckgo":
        return DuckDuckGoHtmlSearchProvider()
    if settings.search_provider == "brave":
        return BraveSearchProvider()
    if settings.search_provider == "tavily":
        return TavilySearchProvider()
    if settings.search_api_key:
        return TavilySearchProvider()
    return DuckDuckGoHtmlSearchProvider()
