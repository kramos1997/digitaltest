"""Document ranking and scoring module."""

import re
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter

from .models import ScrapedDoc
from .config import get_settings
from .utils import log_structured


settings = get_settings()


async def score_documents(query: str, documents: List[ScrapedDoc]) -> List[ScrapedDoc]:
    """
    Score and rank documents using heuristic methods.
    
    Args:
        query: Original search query
        documents: List of scraped documents
        
    Returns:
        List of documents sorted by relevance score (highest first)
    """
    if not documents:
        return documents
    
    query_terms = _normalize_query(query)
    
    scored_docs = []
    for doc in documents:
        score = _calculate_document_score(doc, query_terms)
        doc_with_score = doc.copy()
        doc_with_score.relevance_score = score
        scored_docs.append(doc_with_score)
    
    # Apply diversity penalty
    scored_docs = _apply_diversity_penalty(scored_docs)
    
    # Sort by final score
    ranked_docs = sorted(scored_docs, key=lambda x: x.relevance_score, reverse=True)
    
    log_structured("ranking_complete", {
        "documents_scored": len(scored_docs),
        "top_score": ranked_docs[0].relevance_score if ranked_docs else 0,
        "score_range": f"{ranked_docs[-1].relevance_score:.2f} - {ranked_docs[0].relevance_score:.2f}" if ranked_docs else "N/A"
    })
    
    return ranked_docs


async def rerank_with_llm(query: str, documents: List[ScrapedDoc], llm_client) -> List[ScrapedDoc]:
    """
    Rerank top documents using LLM evaluation.
    
    Args:
        query: Original search query  
        documents: List of top-ranked documents
        llm_client: LLM client instance
        
    Returns:
        List of documents reranked by LLM
    """
    if not documents or len(documents) < 5:
        return documents
    
    try:
        # Prepare document summaries for LLM
        doc_summaries = []
        for i, doc in enumerate(documents[:20]):  # Limit to top 20 for LLM
            summary = _create_document_summary(doc, i+1)
            doc_summaries.append(summary)
        
        # Create reranking prompt
        prompt = _create_rerank_prompt(query, doc_summaries)
        
        messages = [
            {"role": "system", "content": "You are an expert research assistant. Rank documents by their relevance to the query."},
            {"role": "user", "content": prompt}
        ]
        
        # Get LLM response
        response_chunks = []
        async for chunk in llm_client.chat(messages, temperature=0.1, max_tokens=500):
            response_chunks.append(chunk)
        
        llm_response = "".join(response_chunks)
        
        # Parse LLM ranking
        llm_ranking = _parse_llm_ranking(llm_response)
        
        # Merge with heuristic scores
        reranked_docs = _merge_rankings(documents, llm_ranking)
        
        log_structured("llm_rerank_complete", {
            "documents_reranked": len(reranked_docs),
            "llm_ranking_count": len(llm_ranking)
        })
        
        return reranked_docs
        
    except Exception as e:
        log_structured("llm_rerank_error", {"error": str(e)})
        return documents  # Fallback to heuristic ranking


def _normalize_query(query: str) -> List[str]:
    """Normalize query into searchable terms."""
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'what', 'when', 'where', 'why', 'how', 'which'
    }
    
    # Extract meaningful terms
    terms = re.findall(r'\b\w+\b', query.lower())
    terms = [term for term in terms if term not in stop_words and len(term) > 2]
    
    return terms


def _calculate_document_score(doc: ScrapedDoc, query_terms: List[str]) -> float:
    """Calculate comprehensive document relevance score."""
    
    # Component scores
    relevance_score = _calculate_relevance_score(doc, query_terms)
    domain_score = _calculate_domain_score(doc.domain)
    recency_score = _calculate_recency_score(doc.published_at_guess)
    length_score = _calculate_length_score(doc.word_count)
    
    # Weighted combination
    final_score = (
        relevance_score * 0.4 +
        domain_score * 0.3 +
        recency_score * 0.2 +
        length_score * 0.1
    )
    
    return final_score


def _calculate_relevance_score(doc: ScrapedDoc, query_terms: List[str]) -> float:
    """Calculate BM25-inspired relevance score."""
    if not query_terms:
        return 0.0
    
    # Combine title and content, with title weighted higher
    title_text = (doc.title or "").lower()
    content_text = doc.text.lower()
    
    # BM25 parameters
    k1, b = 1.2, 0.75
    
    # Document frequency calculations
    title_words = title_text.split()
    content_words = content_text.split()
    all_words = title_words + content_words
    
    if not all_words:
        return 0.0
    
    word_counts = Counter(all_words)
    doc_length = len(all_words)
    avg_doc_length = 500  # Assumed average
    
    score = 0.0
    for term in query_terms:
        # Term frequency in document
        tf = word_counts.get(term, 0)
        
        # Title boost
        title_tf = title_text.count(term)
        tf += title_tf * 2  # Title matches worth 3x
        
        if tf > 0:
            # BM25 formula
            term_score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avg_doc_length)))
            score += term_score
    
    return score


def _calculate_domain_score(domain: str) -> float:
    """Score domains by authority and trustworthiness."""
    if not domain:
        return 0.5
    
    domain = domain.lower()
    
    # High authority domains
    if any(suffix in domain for suffix in ['.gov', '.mil']):
        return 1.0
    elif any(suffix in domain for suffix in ['.edu', '.ac.uk', '.europa.eu']):
        return 0.95
    elif any(suffix in domain for suffix in ['.org', '.int']):
        return 0.85
    elif any(name in domain for name in ['reuters', 'bbc', 'economist', 'nature', 'science']):
        return 0.8
    elif any(name in domain for name in ['wikipedia', 'arxiv', 'pubmed']):
        return 0.75
    elif any(name in domain for name in ['techcrunch', 'wired', 'arstechnica']):
        return 0.7
    else:
        # Default score for other domains
        return 0.6


def _calculate_recency_score(published_date: Optional[str]) -> float:
    """Score documents by recency (more recent = higher score)."""
    if not published_date:
        return 0.5  # Neutral score for unknown dates
    
    try:
        # Try to parse the date
        from dateutil import parser
        pub_date = parser.parse(published_date)
        now = datetime.now()
        
        # Calculate months difference
        months_diff = (now.year - pub_date.year) * 12 + (now.month - pub_date.month)
        
        # Scoring function: newer = better, with diminishing returns
        if months_diff <= 3:
            return 1.0
        elif months_diff <= 12:
            return 0.8
        elif months_diff <= 24:
            return 0.6
        else:
            return 0.4
            
    except Exception:
        return 0.5  # Default for unparseable dates


def _calculate_length_score(word_count: int) -> float:
    """Score documents by length (prefer substantial but not excessive content)."""
    if word_count < 100:
        return 0.3  # Too short
    elif word_count < 500:
        return 0.7  # Short but acceptable
    elif word_count < 2000:
        return 1.0  # Ideal length
    elif word_count < 5000:
        return 0.8  # Long but manageable
    else:
        return 0.6  # Very long, might be noisy


def _apply_diversity_penalty(documents: List[ScrapedDoc]) -> List[ScrapedDoc]:
    """Apply penalty for too many documents from the same domain."""
    domain_counts = Counter()
    
    for doc in documents:
        domain_counts[doc.domain] += 1
    
    # Apply penalty to domains with many documents
    for doc in documents:
        domain_count = domain_counts[doc.domain]
        if domain_count > 2:
            # Reduce score for additional documents from same domain
            penalty = 0.9 ** (domain_count - 2)
            doc.relevance_score *= penalty
    
    return documents


def _create_document_summary(doc: ScrapedDoc, index: int) -> str:
    """Create a summary of document for LLM reranking."""
    title = doc.title or "Untitled"
    domain = doc.domain or "unknown"
    text_preview = doc.text[:300] + "..." if len(doc.text) > 300 else doc.text
    
    return f"""
{index}. {title}
Domain: {domain}
Date: {doc.published_at_guess or 'Unknown'}
Preview: {text_preview}
"""


def _create_rerank_prompt(query: str, doc_summaries: List[str]) -> str:
    """Create prompt for LLM reranking."""
    summaries_text = "\n".join(doc_summaries)
    
    return f"""Query: "{query}"

Please rank the following documents by their relevance to the query. Consider:
1. Direct relevance to the query topic
2. Authority and credibility of the source
3. Recency and currency of information
4. Depth and quality of content

Documents:
{summaries_text}

Respond with a ranked list of document numbers (most relevant first), with brief reasoning:
Example: "1, 5, 3, 2, 4 - Document 1 directly addresses the query with recent data from an authoritative source..."
"""


def _parse_llm_ranking(response: str) -> List[int]:
    """Parse LLM ranking response to extract document order."""
    # Look for number sequences in the response
    numbers = re.findall(r'\b(\d+)\b', response)
    
    try:
        # Convert to integers and remove duplicates while preserving order
        seen = set()
        ranking = []
        for num_str in numbers:
            num = int(num_str)
            if num not in seen and 1 <= num <= 20:  # Valid document numbers
                ranking.append(num)
                seen.add(num)
        
        return ranking
    except Exception:
        return []


def _merge_rankings(documents: List[ScrapedDoc], llm_ranking: List[int]) -> List[ScrapedDoc]:
    """Merge LLM ranking with heuristic scores."""
    if not llm_ranking:
        return documents
    
    # Create a mapping of original positions
    doc_mapping = {i+1: doc for i, doc in enumerate(documents)}
    
    # Apply LLM ranking with fallback to heuristic ranking
    reranked = []
    used_docs = set()
    
    # First, add documents in LLM order with boosted scores
    for llm_pos, doc_num in enumerate(llm_ranking):
        if doc_num in doc_mapping:
            doc = doc_mapping[doc_num]
            # Boost score based on LLM position
            boost_factor = 1.0 + (0.1 * (len(llm_ranking) - llm_pos))
            doc.relevance_score *= boost_factor
            reranked.append(doc)
            used_docs.add(doc_num)
    
    # Add remaining documents in original heuristic order
    for i, doc in enumerate(documents):
        if (i+1) not in used_docs:
            reranked.append(doc)
    
    return reranked
