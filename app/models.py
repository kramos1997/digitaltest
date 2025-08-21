"""Pydantic models for request/response data structures."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime


class ResearchRequest(BaseModel):
    """Request model for research queries."""
    
    q: str = Field(..., min_length=1, max_length=500, description="Research query")
    lang: str = Field("en", pattern="^(en|de)$", description="Language preference")


class SearchResult(BaseModel):
    """Individual search result from SearXNG."""
    
    title: str
    url: str
    snippet: str
    engine: str
    published_date: Optional[str] = None
    domain: str


class ScrapedDoc(BaseModel):
    """Scraped document with extracted content."""
    
    title: Optional[str] = None
    url: str
    text: str
    published_at_guess: Optional[str] = None
    domain: str
    word_count: int = 0
    relevance_score: float = 0.0


class SourceInfo(BaseModel):
    """Source information for response."""
    
    id: int
    title: str
    url: str
    domain: str
    published_date: str
    pull_quotes: List[str] = []


class EvidenceEntry(BaseModel):
    """Evidence matrix entry."""
    
    claim: str
    supporting_quote: str
    source_id: int
    source_url: str
    source_title: str
    source_date: str
    confidence: str  # "high", "medium", "low"


class ProcessingStats(BaseModel):
    """Research processing statistics."""
    
    sources_found: int = 0
    sources_used: int = 0
    queries_expanded: int = 0
    processing_time_seconds: Optional[float] = None


class ResearchResponse(BaseModel):
    """Complete research response."""
    
    answer: str
    sources: List[SourceInfo]
    evidence_matrix: List[EvidenceEntry] = []
    expanded_queries: List[str] = []
    processing_stats: ProcessingStats
    confidence: str  # "high", "medium", "low", "none"
    citations_count: int = 0
    factcheck_status: str = "unknown"  # "passed", "revised", "failed"


class ValidationIssue(BaseModel):
    """Answer validation issue."""
    
    claim: str
    issue: str
    severity: str  # "high", "medium", "low"


class LLMHealthResponse(BaseModel):
    """LLM health check response."""
    
    status: str  # "healthy", "unhealthy"
    provider: str
    model: Optional[str] = None
    test_response: Optional[str] = None
    error: Optional[str] = None
