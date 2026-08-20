"""
Web search tool for company research.

Uses Tavily API (recommended) or Serper API for web search.
This allows the agent to look up company information to personalize
cover letters with specific details about the company's mission,
products, recent news, etc.

Interview line: "I added a web search tool so the agent can personalize
cover letters with real company information, not just generic statements.
This required handling external API rate limits and response parsing."
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import httpx

from app.core.config import settings


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    content: Optional[str] = None  # Full content if available


class WebSearchTool:
    """
    Web search tool using Tavily or Serper API.

    Tavily is recommended because:
    - Optimized for AI agents (returns structured, clean results)
    - Includes content extraction
    - Handles rate limiting gracefully

    Serper is a cheaper alternative:
    - Google Search API wrapper
    - Faster but less structured output
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
        prefer_tavily: bool = True
    ):
        self.tavily_api_key = tavily_api_key
        self.serper_api_key = serper_api_key
        self.prefer_tavily = prefer_tavily

    async def search_tavily(
        self,
        query: str,
        max_results: int = 5
    ) -> List[SearchResult]:
        """
        Search using Tavily API.

        Tavily is purpose-built for AI agents and returns
        cleaner, more structured results than raw search APIs.
        """
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": f"Bearer {self.tavily_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": query,
                    "max_results": max_results,
                    "include_raw_content": False,
                    "search_depth": "basic"  # "basic" or "advanced"
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Tavily API error: {response.status_code}")

            data = response.json()
            results = []

            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    content=item.get("raw_content")
                ))

            return results

    async def search_serper(
        self,
        query: str,
        max_results: int = 5
    ) -> List[SearchResult]:
        """
        Search using Serper API (Google Search wrapper).

        Cheaper than Tavily but returns less structured results.
        Good fallback option.
        """
        if not self.serper_api_key:
            raise ValueError("SERPER_API_KEY not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "num": max_results
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Serper API error: {response.status_code}")

            data = response.json()
            results = []

            # Serper returns organic results in "organic" key
            for item in data.get("organic", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", "")
                ))

            return results

    async def search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[SearchResult]:
        """
        Main search entry point.

        Tries Tavily first (if preferred and available),
        falls back to Serper.
        """
        if self.prefer_tavily and self.tavily_api_key:
            try:
                return await self.search_tavily(query, max_results)
            except Exception as e:
                print(f"Tavily search failed: {e}")

        if self.serper_api_key:
            try:
                return await self.search_serper(query, max_results)
            except Exception as e:
                print(f"Serper search failed: {e}")

        # No API configured - return empty results
        print("Warning: No web search API configured")
        return []

    async def research_company(self, company_name: str) -> Dict[str, Any]:
        """
        Research a company for cover letter personalization.

        Returns structured information about:
        - What the company does (mission/products)
        - Recent news or announcements
        - Company culture/values (if available)

        Args:
            company_name: Name of the company to research

        Returns:
            Dict with company research summary
        """
        # Run multiple searches in parallel
        queries = [
            f"{company_name} company mission values products",
            f"{company_name} recent news 2024 2025",
            f"{company_name} engineering team culture",
        ]

        results = []
        for query in queries:
            search_results = await self.search(query, max_results=3)
            results.extend(search_results)

        # Compile into a research summary
        if not results:
            return {
                "company_name": company_name,
                "summary": "No information found.",
                "sources": []
            }

        # Combine snippets into a summary
        summary_parts = []
        sources = []

        for r in results[:6]:
            if r.snippet:
                summary_parts.append(f"- {r.snippet}")
                sources.append({"title": r.title, "url": r.url})

        return {
            "company_name": company_name,
            "summary": "\n".join(summary_parts),
            "sources": sources
        }


# Global instance
_web_search_tool: Optional[WebSearchTool] = None


def get_web_search_tool() -> WebSearchTool:
    """Get or create the global web search tool instance."""
    global _web_search_tool
    if _web_search_tool is None:
        _web_search_tool = WebSearchTool(
            tavily_api_key=getattr(settings, 'tavily_api_key', None),
            serper_api_key=getattr(settings, 'serper_api_key', None)
        )
    return _web_search_tool


async def search_web(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    Convenience function for web search.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    tool = get_web_search_tool()
    return await tool.search(query, max_results)


async def research_company(company_name: str) -> Dict[str, Any]:
    """
    Convenience function for company research.

    Args:
        company_name: Company to research

    Returns:
        Company research summary
    """
    tool = get_web_search_tool()
    return await tool.research_company(company_name)
