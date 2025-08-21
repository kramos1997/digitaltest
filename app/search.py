"""Query expansion and SearXNG search client."""

import asyncio
import json
from typing import List, Dict, Any
from urllib.parse import urlencode
import httpx

from .models import SearchResult
from .config import get_settings
from .utils import log_structured


settings = get_settings()


async def expand_query(query: str) -> List[str]:
    """
    Expand a query into 4-8 sub-queries with various strategies.
    
    Args:
        query: Original search query
        
    Returns:
        List of expanded query strings
    """
    base_query = query.strip()
    expanded = [base_query]  # Always include original
    
    # Strategy 1: Add temporal constraints
    expanded.append(f"{base_query} since:2023")
    expanded.append(f"{base_query} last 24 months")
    
    # Strategy 2: Domain bias for authoritative sources
    expanded.append(f"site:gov {base_query}")
    expanded.append(f"site:europa.eu {base_query}")
    expanded.append(f"site:edu {base_query}")
    
    # Strategy 3: Add context terms
    if "regulation" not in base_query.lower():
        expanded.append(f"{base_query} regulation compliance")
    
    if "policy" not in base_query.lower():
        expanded.append(f"{base_query} policy guidelines")
    
    # Strategy 4: Broader and narrower variants
    expanded.append(f"{base_query} overview")
    expanded.append(f"{base_query} implementation details")
    
    # Remove duplicates and limit to 8
    unique_queries = list(dict.fromkeys(expanded))[:8]
    
    log_structured("query_expansion", {
        "original": base_query,
        "expanded_count": len(unique_queries),
        "queries": unique_queries
    })
    
    return unique_queries


async def searx_search(queries: List[str], client: httpx.AsyncClient, k: int = 8) -> List[SearchResult]:
    """
    Search using SearXNG with multiple queries and deduplicate results.
    
    Args:
        queries: List of search queries
        client: HTTP client for requests
        k: Maximum number of results to return
        
    Returns:
        List of unique SearchResult objects
    """
    all_results = []
    seen_urls = set()
    
    # Execute searches with limited concurrency
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent searches
    
    async def search_single_query(query: str) -> List[SearchResult]:
        async with semaphore:
            try:
                params = {
                    'q': query,
                    'format': 'json',
                    'engines': 'google,bing,duckduckgo',  # Multiple engines for diversity
                    'safesearch': 1,
                    'time_range': '',  # Let individual queries handle time constraints
                }
                
                url = f"{settings.searx_url}/search"
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                results = []
                
                for item in data.get('results', []):
                    # Basic deduplication by URL
                    clean_url = _clean_url(item.get('url', ''))
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)
                    
                    # Parse date if available
                    published_date = _parse_date(item.get('publishedDate', ''))
                    
                    result = SearchResult(
                        title=item.get('title', '').strip(),
                        url=clean_url,
                        snippet=item.get('content', '').strip(),
                        engine=item.get('engine', 'unknown'),
                        published_date=published_date,
                        domain=_extract_domain(clean_url)
                    )
                    results.append(result)
                
                return results
                
            except Exception as e:
                log_structured("search_error", {
                    "query": query,
                    "error": str(e)
                })
                return []
    
    # Execute all searches
    search_tasks = [search_single_query(q) for q in queries]
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    # Flatten results and apply diversity scoring
    for results in search_results:
        if isinstance(results, list):
            all_results.extend(results)
    
    # Apply diversity and quality filtering
    filtered_results = _apply_diversity_filter(all_results)
    
    log_structured("search_complete", {
        "queries_count": len(queries),
        "total_results": len(all_results),
        "filtered_results": len(filtered_results),
        "returning": min(k, len(filtered_results))
    })
    
    return filtered_results[:k]


def _clean_url(url: str) -> str:
    """Clean and normalize URL for deduplication."""
    if not url:
        return ""
    
    # Remove common tracking parameters
    import re
    url = re.sub(r'[?&](utm_|fbclid|gclid|ref=)', '?', url)
    url = re.sub(r'\?&', '?', url)
    url = re.sub(r'[?&]$', '', url)
    
    return url


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().replace('www.', '')
    except:
        return ""


def _parse_date(date_str: str) -> str:
    """Parse and normalize date string."""
    if not date_str:
        return ""
    
    try:
        from dateutil import parser
        parsed_date = parser.parse(date_str)
        return parsed_date.strftime('%Y-%m')
    except:
        return date_str


def _apply_diversity_filter(results: List[SearchResult]) -> List[SearchResult]:
    """
    Apply diversity filtering to avoid too many results from the same domain.
    """
    if not results:
        return results
    
    domain_counts = {}
    filtered_results = []
    
    # Sort by domain quality first (gov/edu domains get priority)
    def domain_priority(result):
        domain = result.domain
        if any(tld in domain for tld in ['.gov', '.europa.eu', '.edu']):
            return 0  # Highest priority
        elif any(tld in domain for tld in ['.org', '.int']):
            return 1  # Medium priority
        else:
            return 2  # Normal priority
    
    sorted_results = sorted(results, key=domain_priority)
    
    for result in sorted_results:
        domain = result.domain
        
        # Limit results per domain (more for high-quality domains)
        max_per_domain = 3 if domain_priority(result) == 0 else 2
        
        if domain_counts.get(domain, 0) < max_per_domain:
            filtered_results.append(result)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
    
    return filtered_results
