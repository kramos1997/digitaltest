"""Web scraping and content extraction module."""

import asyncio
import re
from typing import List, Optional
from urllib.parse import urlparse, urljoin
import httpx
from readability import Document
import trafilatura
from bs4 import BeautifulSoup

from .models import SearchResult, ScrapedDoc
from .config import get_settings
from .utils import log_structured


settings = get_settings()


async def scrape_documents(search_results: List[SearchResult]) -> List[ScrapedDoc]:
    """
    Scrape and extract clean text from search results.
    
    Args:
        search_results: List of search results to scrape
        
    Returns:
        List of scraped documents with cleaned text
    """
    semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
    
    async def scrape_single_doc(result: SearchResult) -> Optional[ScrapedDoc]:
        async with semaphore:
            try:
                return await _scrape_single_document(result)
            except Exception as e:
                log_structured("scrape_error", {
                    "url": result.url,
                    "error": str(e)
                })
                return None
    
    # Execute all scraping tasks
    scrape_tasks = [scrape_single_doc(result) for result in search_results]
    scraped_docs = await asyncio.gather(*scrape_tasks, return_exceptions=True)
    
    # Filter out failed scrapes and exceptions
    valid_docs = []
    for doc in scraped_docs:
        if isinstance(doc, ScrapedDoc) and doc.text.strip():
            valid_docs.append(doc)
    
    log_structured("scrape_complete", {
        "attempted": len(search_results),
        "successful": len(valid_docs)
    })
    
    return valid_docs


async def _scrape_single_document(search_result: SearchResult) -> Optional[ScrapedDoc]:
    """Scrape a single document with multiple extraction strategies."""
    
    # Check robots.txt compliance (basic check)
    if not _is_scrapable_url(search_result.url):
        log_structured("scrape_blocked", {"url": search_result.url, "reason": "robots.txt"})
        return None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ClarityDesk/1.0; +https://claritydesk.example.com/bot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        headers=headers,
        follow_redirects=True
    ) as client:
        try:
            response = await client.get(search_result.url)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                return None
            
            html_content = response.text
            
            # Extract main content using multiple methods
            extracted_text = _extract_main_content(html_content, search_result.url)
            
            if not extracted_text or len(extracted_text.strip()) < 100:
                return None
            
            # Extract metadata
            title, published_date = _extract_metadata(html_content, search_result)
            
            # Language detection (basic)
            if not _is_supported_language(extracted_text):
                return None
            
            # Clean and normalize text
            cleaned_text = _clean_text(extracted_text)
            
            doc = ScrapedDoc(
                title=title or search_result.title,
                url=search_result.url,
                text=cleaned_text,
                published_at_guess=published_date or search_result.published_date,
                domain=search_result.domain,
                word_count=len(cleaned_text.split())
            )
            
            return doc
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [403, 404, 429, 503]:
                log_structured("scrape_blocked", {
                    "url": search_result.url, 
                    "status": e.response.status_code
                })
            return None
        except Exception as e:
            log_structured("scrape_error", {
                "url": search_result.url,
                "error": str(e)
            })
            return None


def _extract_main_content(html: str, url: str) -> str:
    """Extract main content using readability and trafilatura."""
    
    # Method 1: Try readability-lxml
    try:
        doc = Document(html)
        readability_text = doc.summary()
        if readability_text:
            # Convert HTML to text
            soup = BeautifulSoup(readability_text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            if len(text) > 200:
                return text
    except Exception as e:
        log_structured("readability_failed", {"url": url, "error": str(e)})
    
    # Method 2: Try trafilatura
    try:
        trafilatura_text = trafilatura.extract(html)
        if trafilatura_text and len(trafilatura_text) > 200:
            return trafilatura_text
    except Exception as e:
        log_structured("trafilatura_failed", {"url": url, "error": str(e)})
    
    # Method 3: Basic BeautifulSoup fallback
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script, style, nav, footer, etc.
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Look for main content areas
        main_content = None
        for selector in ['main', 'article', '[role="main"]', '.content', '.post', '.entry']:
            content = soup.select_one(selector)
            if content:
                main_content = content
                break
        
        if not main_content:
            main_content = soup.body or soup
        
        text = main_content.get_text(separator=' ', strip=True)
        return text
        
    except Exception as e:
        log_structured("fallback_extraction_failed", {"url": url, "error": str(e)})
        return ""


def _extract_metadata(html: str, search_result: SearchResult) -> tuple[Optional[str], Optional[str]]:
    """Extract title and published date from HTML metadata."""
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        title = None
        
        # Try various title sources in order of preference
        title_sources = [
            soup.find('meta', property='og:title'),
            soup.find('meta', name='twitter:title'),
            soup.find('title'),
            soup.find('h1')
        ]
        
        for source in title_sources:
            if source:
                if source.name == 'meta':
                    title = source.get('content', '').strip()
                else:
                    title = source.get_text(strip=True)
                if title:
                    break
        
        # Extract published date
        published_date = None
        
        date_selectors = [
            ('meta', 'property', 'article:published_time'),
            ('meta', 'name', 'publishedDate'),
            ('meta', 'name', 'date'),
            ('time', 'datetime', None)
        ]
        
        for tag, attr, value in date_selectors:
            if value:
                element = soup.find(tag, {attr: value})
            else:
                element = soup.find(tag, attrs={attr: True})
            
            if element:
                if tag == 'meta':
                    published_date = element.get('content', '').strip()
                else:
                    published_date = element.get('datetime', '').strip()
                if published_date:
                    break
        
        # Try to parse date patterns in text
        if not published_date:
            published_date = _extract_date_from_text(html)
        
        return title, published_date
        
    except Exception:
        return None, None


def _extract_date_from_text(html: str) -> Optional[str]:
    """Extract date patterns from HTML text."""
    
    # Common date patterns
    date_patterns = [
        r'\b(\d{4}-\d{2}-\d{2})\b',  # 2024-03-15
        r'\b(\w+\s+\d{1,2},\s+\d{4})\b',  # March 15, 2024
        r'\b(\d{1,2}\s+\w+\s+\d{4})\b',  # 15 March 2024
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, html)
        if matches:
            return matches[0]
    
    return None


def _is_supported_language(text: str) -> bool:
    """Basic language detection to filter non-supported content."""
    
    # Simple heuristic: check for common English/German words
    english_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    german_words = {'der', 'die', 'das', 'und', 'oder', 'aber', 'in', 'an', 'zu', 'für', 'von', 'mit'}
    
    words = set(text.lower().split()[:100])  # Check first 100 words
    
    english_count = len(words & english_words)
    german_count = len(words & german_words)
    
    # If we find at least 3 common words, consider it supported
    return (english_count >= 3) or (german_count >= 3)


def _clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common website clutter
    text = re.sub(r'Cookie\s+(?:Policy|Notice|Settings).*?(?:\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Privacy\s+Policy.*?(?:\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Terms\s+of\s+Service.*?(?:\n|$)', '', text, flags=re.IGNORECASE)
    
    # Remove navigation artifacts
    text = re.sub(r'\b(?:Home|About|Contact|Menu|Login|Register|Subscribe)\b\s*', '', text)
    
    # Remove excessive punctuation
    text = re.sub(r'[.]{3,}', '...', text)
    text = re.sub(r'[-_]{3,}', '---', text)
    
    return text.strip()


def _is_scrapable_url(url: str) -> bool:
    """Basic check if URL is scrapable (robots.txt consideration)."""
    
    try:
        parsed = urlparse(url)
        
        # Skip known problematic domains
        blocked_domains = {
            'facebook.com', 'twitter.com', 'linkedin.com', 
            'instagram.com', 'tiktok.com'
        }
        
        domain = parsed.netloc.lower().replace('www.', '')
        if domain in blocked_domains:
            return False
        
        # Skip PDF and other document types
        if url.lower().endswith(('.pdf', '.doc', '.docx', '.ppt', '.pptx')):
            return False
        
        return True
        
    except Exception:
        return False
