import logging
import os

from src.data.models import ExaSearchResult

logger = logging.getLogger(__name__)

try:
    from exa_py import Exa
except ImportError:
    Exa = None


def search_exa(
    query: str,
    num_results: int = 10,
    search_type: str = "auto",
    category: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_text: list[str] | None = None,
    exclude_text: list[str] | None = None,
    start_published_date: str | None = None,
    end_published_date: str | None = None,
    api_key: str | None = None,
) -> list[ExaSearchResult]:
    """Search the web using Exa's AI-powered search engine.

    Args:
        query: The search query.
        num_results: Number of results to return (max 100).
        search_type: Search type - 'auto', 'neural', 'fast', or 'instant'.
        category: Filter by category (e.g. 'news', 'company', 'research paper',
                  'financial report').
        include_domains: Only include results from these domains.
        exclude_domains: Exclude results from these domains.
        include_text: Strings that must appear in page text.
        exclude_text: Strings to exclude from results.
        start_published_date: ISO 8601 date; only results published after this.
        end_published_date: ISO 8601 date; only results published before this.
        api_key: Exa API key. Falls back to EXA_API_KEY env var.

    Returns:
        List of ExaSearchResult objects.
    """
    if Exa is None:
        logger.warning("exa-py package not installed. Run: pip install exa-py")
        return []

    exa_api_key = api_key or os.environ.get("EXA_API_KEY")
    if not exa_api_key:
        logger.warning("EXA_API_KEY not set. Exa search will return empty results.")
        return []

    try:
        client = Exa(api_key=exa_api_key)
        client.headers["x-exa-integration"] = "ai-hedge-fund"

        search_kwargs: dict = {
            "query": query,
            "num_results": num_results,
            "type": search_type,
            "contents": {
                "highlights": {"max_characters": 4000},
                "summary": True,
            },
        }

        if category:
            search_kwargs["category"] = category
        if include_domains:
            search_kwargs["include_domains"] = include_domains
        if exclude_domains:
            search_kwargs["exclude_domains"] = exclude_domains
        if include_text:
            search_kwargs["include_text"] = include_text
        if exclude_text:
            search_kwargs["exclude_text"] = exclude_text
        if start_published_date:
            search_kwargs["start_published_date"] = start_published_date
        if end_published_date:
            search_kwargs["end_published_date"] = end_published_date

        response = client.search(**search_kwargs)

        results = []
        for result in response.results:
            title = getattr(result, "title", None) or ""
            url = getattr(result, "url", None) or ""
            published_date = getattr(result, "published_date", None)
            author = getattr(result, "author", None)

            # Build content snippet from highlights and summary
            highlights = getattr(result, "highlights", None) or []
            summary = getattr(result, "summary", None) or ""
            text = getattr(result, "text", None) or ""

            if highlights:
                snippet = "\n".join(highlights)
            elif summary:
                snippet = summary
            elif text:
                snippet = text[:2000]
            else:
                snippet = ""

            results.append(
                ExaSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    published_date=published_date,
                    author=author,
                )
            )

        return results

    except Exception as e:
        logger.warning("Exa search failed for query '%s': %s", query, e)
        return []
