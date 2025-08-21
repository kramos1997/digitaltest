"""Data models for the research system."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl
from enum import Enum


class ResearchDepth(str, Enum):
    """Research depth options."""
    QUICK = "quick"
    STANDARD = "standard" 
    COMPREHENSIVE = "comprehensive"


class QueryType(str, Enum):
    """Types of queries the system can handle."""
    FACTUAL = "factual"
    LIST = "list"
    COMPARISON = "comparison"
    ANALYSIS = "analysis"
    HOW_TO = "how_to"


class ResearchOptions(BaseModel):
    """Options for research requests."""
    depth: ResearchDepth = ResearchDepth.STANDARD
    max_sources: int = 20
    include_contact_info: bool = False
    research_timeout: int = 300


class ResearchRequest(BaseModel):
    """Request model for research endpoint."""
    query: str
    options: Optional[ResearchOptions] = ResearchOptions()


class SearchResult(BaseModel):
    """Individual search result."""
    title: str
    url: HttpUrl
    snippet: str
    domain: str
    rank: int


class ExtractedContent(BaseModel):
    """Content extracted from a webpage."""
    url: HttpUrl
    title: str
    content: str
    metadata: Dict[str, Any]
    extraction_success: bool
    extraction_time: float


class ProcessedSource(BaseModel):
    """A source after processing and quality assessment."""
    title: str
    url: HttpUrl
    relevance_score: float
    key_findings: str
    domain: str
    last_updated: Optional[str] = None
    content_length: int
    quality_score: float


class ResearchMetadata(BaseModel):
    """Metadata about the research process."""
    sources_searched: int
    sources_processed: int
    research_time_seconds: float
    confidence_score: float
    query_type: QueryType
    sub_questions: List[str]


class ResearchResponse(BaseModel):
    """Response model for research endpoint."""
    query: str
    answer: str
    research_metadata: ResearchMetadata
    sources: List[ProcessedSource]
    follow_up_suggestions: List[str]


class QueryAnalysis(BaseModel):
    """Analysis of the user's query."""
    original_query: str
    query_type: QueryType
    key_entities: List[str]
    sub_questions: List[str]
    search_terms: List[str]
    intent: str